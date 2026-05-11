import streamlit as st
import ast
from helpers.db import get_recipe_by_id, get_ingredients_for_recipe
from helpers.switch_page import switch_page
from helpers.image_helper import display_recipe_image
from helpers.supabase_client import mark_recipe_seen, save_recipe, mark_recipe_cooked
from helpers.nutrition_helper import get_past_7_days_nutrition, draw_nutrition_radar, get_recipe_nutrition, get_todays_nutrition



@st.fragment
def show_image_fragment(recipe_title, recipe_id):
    # Rendering the image in a fragment lets Streamlit refresh this part separately
    # from the rest of the recipe details page.
    with st.spinner("Finding image..."):
        display_recipe_image(recipe_title, key_suffix=f"details_{recipe_id}")

@st.fragment
def show_nutrition_fragment(recipe_id, user_id):
    # Keeping nutrition in its own fragment prevents slow Gemini/Supabase work from
    # blocking the rest of the recipe details layout more than necessary.
    with st.spinner("Calculating nutrition impact..."):
        # Caching the nutrition estimate in session state avoids recalculating it
        # every time Streamlit reruns this page.
        nut_cache_key = f"nut_data_{recipe_id}"
        if nut_cache_key not in st.session_state:
            st.session_state[nut_cache_key] = get_recipe_nutrition(recipe_id)
        
        recipe_nut = st.session_state[nut_cache_key]
        # Today's nutrition is used as the baseline, so the projection shows
        # today plus this recipe rather than a separate weekly total.
        today_info = get_todays_nutrition(user_id)
        
        st.subheader("Nutrition Impact (Weekly % DV)")
        
        if not recipe_nut or all(v == 0 for v in recipe_nut.values()):
            # Zero-values usually mean the Gemini estimate failed or quota was reached,
            # so the user should not treat the chart as reliable nutrition data.
            st.warning("Nutrition data momentarily unavailable (API Quota Reached).")
        
        fig = draw_nutrition_radar(
            today_stats=today_info["totals"], 
            projected_recipe_nut=recipe_nut
        )
        st.plotly_chart(fig, use_container_width=True, config={'staticPlot': True})

def show():
    # Recipe Details depends on the selected recipe stored during navigation from
    # search, home, profile, or scan results.
    recipe_id = st.session_state.get('selected_recipe', None)
    user_id = st.session_state.get("user_id")

    if recipe_id is None:
        # This guard prevents the page from crashing if opened directly without
        # a selected recipe in session state.
        st.warning("No recipe selected.")
        return
    
    recipe = get_recipe_by_id(recipe_id)
    if not recipe:
        # A missing recipe can happen if an old id is still in session state but
        # the database row no longer exists.
        st.error("Recipe not found in the database.")
        return

    recipe_title = recipe.get("recipe_title", "Unknown Recipe")

    # Splitting the top section gives the image and the main recipe information
    # equal visual weight.
    picture_col, details_col = st.columns(2)
    
    with picture_col:
        st.write("") # Spacer
        show_image_fragment(recipe_title, recipe_id)

    with details_col:
        st.title(recipe_title)
        st.write("") # Spacer
        st.write(f"**Description:** {recipe.get('description', '')}")
        st.write(f"⏱️ **Prep time:** {recipe.get('est_prep_time_min', 0)} mins | **Cook time:** {recipe.get('est_cook_time_min', 0)} mins")
        
        st.write("")
        # Starting the guide also marks the recipe as cooked, since entering the
        # guide represents beginning the cooking flow.
        st.button(
            "🧑‍🍳 Start Interactive Cooking Guide", 
            type="primary", 
            use_container_width=True, 
            key=f"guide_btn_{recipe_id}",
            on_click=switch_page,
            args=("Guide", recipe_id, lambda r=recipe_id: mark_recipe_cooked(r))
        )
            
        # Marking cooked and saving to library are separate actions because cooked
        # history and saved recipes are used differently elsewhere in the app.
        col_c, col_s = st.columns(2)
        with col_c:
            st.button(
                "✅ Mark as Cooked", 
                use_container_width=True, 
                key=f"cook_{recipe_id}",
                on_click=mark_recipe_cooked,
                args=(recipe_id,)
            )
        with col_s:
            st.button(
                "💾 Save to Library", 
                use_container_width=True, 
                key=f"save_{recipe_id}",
                on_click=save_recipe,
                args=(recipe_id,)
            )
            
    with st.container():
        # Ingredients and nutrition sit side by side because they explain the recipe
        # from two different angles: what it uses and what it contributes.
        ingredients_col, nut_col = st.columns(2)
        with nut_col:
            show_nutrition_fragment(recipe_id, user_id)
        
        with ingredients_col:
            st.subheader("Ingredients")
            ingredients = get_ingredients_for_recipe(recipe_id)
            if ingredients:
                for ing in ingredients:
                    st.markdown(f"- {ing.get('original_string')} (*Cleaned*: {ing.get('pure_ingredient_harsh', '')})")
            else:
                st.write("No ingredients listed.")
        
    st.subheader("Directions")
    directions_str = recipe.get("directions", "[]")
    try:
        # Directions are stored as a string representation of a list, so literal_eval
        # converts them back into individual steps for display.
        directions = ast.literal_eval(directions_str)
        for idx, step in enumerate(directions, 1):
            st.write(f"**Step {idx}:** {step}")
    except Exception:
        # If parsing fails, displaying the raw directions is still better than
        # hiding the cooking instructions completely.
        st.write(directions_str)
