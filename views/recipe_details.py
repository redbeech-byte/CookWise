import streamlit as st
import ast
from helpers.db import get_recipe_by_id, get_ingredients_for_recipe
from helpers.switch_page import switch_page
from helpers.image_helper import display_recipe_image
from helpers.supabase_client import mark_recipe_seen, save_recipe, mark_recipe_cooked
def show_title():
    return "Cooking Time!"
def show():
    recipe_id = st.session_state.get('selected_recipe', None)

    if recipe_id is None:
        st.warning("No recipe selected.")
        return
    
    # Mark as seen
    mark_recipe_seen(recipe_id)
    
    recipe = get_recipe_by_id(recipe_id)
    if not recipe:
        st.error("Recipe not found in the database.")
        return
        
    recipe_title = recipe.get("recipe_title", "Unknown Recipe")


    picture_col, details_col = st.columns(2)
    
    with picture_col:
        st.space("small")
        display_recipe_image(recipe_title, key_suffix=f"details_{recipe_id}")

    with details_col:
        st.title(recipe_title)
        st.space("small")
        st.write(f"**Description:** {recipe.get('description', '')}")
        st.write(f"⏱️ **Prep time:** {recipe.get('est_prep_time_min', 0)} mins | **Cook time:** {recipe.get('est_cook_time_min', 0)} mins")
        
        st.write("")
        if st.button("🧑‍🍳 Start Interactive Cooking Guide", type="primary", use_container_width=True, key=f"guide_{recipe_id}"):
            switch_page("Guide")
            
        col_c, col_s = st.columns(2)
        with col_c:
            if st.button("✅ Mark as Cooked", use_container_width=True, key=f"cook_{recipe_id}"):
                mark_recipe_cooked(recipe_id)
                st.success("Marked as Cooked!")
        with col_s:
            if st.button("💾 Save to Library", use_container_width=True, key=f"save_{recipe_id}"):
                save_recipe(recipe_id)
                st.success("Saved!")

            
    
    

    
    st.subheader("Ingredients")
    ingredients = get_ingredients_for_recipe(recipe_id)
    if ingredients:
        for ing in ingredients:
            # We can show pure_ingredient_harsh or original_string
            st.markdown(f"- {ing.get('original_string')} (*Cleaned*: {ing.get('pure_ingredient_harsh', ing.get('pure_ingredient_harsh'))})")
    else:
        st.write("No ingredients listed.")
        
    st.subheader("Directions")
    directions_str = recipe.get("directions", "[]")
    try:
        directions = ast.literal_eval(directions_str)
        for idx, step in enumerate(directions, 1):
            st.write(f"**Step {idx}:** {step}")
    except Exception as e:
        st.write(directions_str)
