import streamlit as st
import textwrap
import os
from helpers.switch_page import switch_page
from helpers.db import search_recipes, get_recipe_by_id
from helpers.image_helper import display_recipe_image, get_unique_recipe_image_data
from helpers.supabase_client import get_cooked_recipes, mark_recipe_seen
from helpers.recommendation_helper import get_recommended_recipes
from helpers.nutrition_helper import get_past_7_days_nutrition, draw_nutrition_radar, get_todays_nutrition



def show():
    user_id = st.session_state.get("user_id")
    
    # PRE-FETCH DATA with a single spinner
    with st.spinner("Loading your kitchen..."):
        cooked_recipes = get_cooked_recipes()
        # 7-day representative quality
        avg_info = get_past_7_days_nutrition(user_id)
        # Actual progress strictly today
        today_info = get_todays_nutrition(user_id)
    
    current_guide_id = st.session_state.get("current_recipe_guide")

    graph, spacer1, navigation, spacer2 = st.columns([4, 0.5, 2, 0.5])

    with navigation:
        with st.container():
            if not current_guide_id and not cooked_recipes:
                st.subheader("Welcome to CookWise! 👋")
                st.write("Your personalized cooking assistant. Get started by searching for recipes or uploading your fridge ingredients.")
            elif not current_guide_id and cooked_recipes:
                st.subheader("Welcome back! 👋")
                st.write("Here's the last recipe you cooked:")
                last_cooked_id = cooked_recipes[0]["recipe_id"]
                last_cooked = get_recipe_by_id(last_cooked_id)
                if last_cooked:
                    title = last_cooked.get('recipe_title', 'Unknown Title')
                    display_recipe_image(title, key_suffix="last_cooked")
                    st.write(f"**{title}**")
                    
                    st.button(
                        "👨‍🍳 Continue Cooking", 
                        key="continue_cooking", 
                        use_container_width=True,
                        on_click=switch_page,
                        args=("Guide", last_cooked_id, lambda: mark_recipe_seen(last_cooked_id))
                    )
                    st.button(
                        "View Recipe Details", 
                        key="view_details", 
                        use_container_width=True,
                        on_click=switch_page,
                        args=("Recipe Details", last_cooked_id, lambda: mark_recipe_seen(last_cooked_id))
                    )
            else:
                st.subheader("Continue where you left off:")
                last_cooked = get_recipe_by_id(current_guide_id)
                if last_cooked:
                    title = last_cooked.get('recipe_title', 'Unknown Title')
                    display_recipe_image(title, key_suffix="current_guide")
                    st.write(f"**{title}**")
                    st.button(
                        "👨‍🍳 Continue Cooking", 
                        key="continue_cooking_guide", 
                        use_container_width=True,
                        on_click=switch_page,
                        args=("Guide", current_guide_id, lambda: mark_recipe_seen(current_guide_id))
                    )
                    st.button(
                        "View Recipe Details", 
                        key="view_details_guide", 
                        use_container_width=True,
                        on_click=switch_page,
                        args=("Recipe Details", current_guide_id, lambda: mark_recipe_seen(current_guide_id))
                    )

    with graph:
        st.subheader("Your NutriRadar")
        with st.container(border=True):
            fig = draw_nutrition_radar(
                today_stats=today_info["totals"],
                average_stats=avg_info["totals"]
            )
            st.plotly_chart(fig, use_container_width=True, config={'staticPlot': True})

    recipes = get_recommended_recipes(limit=12)
    if not recipes:
        profile = get_profile()
        dietary = profile.get("dietary_restrictions", []) if profile else []
        cooking = profile.get("cooking_preferences", []) if profile else []
        recipes = search_recipes("", limit=12, dietary_prefs=dietary, cooking_prefs=cooking)

    for r in recipes:
        get_unique_recipe_image_data(r.get('recipe_title', 'recipe'))

    if "carousel_idx" not in st.session_state:
        st.session_state.carousel_idx = 0

    st.divider()
    st.subheader("Recommended Recipes")
    TILES_PER_ROW = 4

    col_prev, col_content, col_next = st.columns([1, 15, 1], vertical_alignment="center")

    with col_prev:
        def prev_carousel():
            st.session_state.carousel_idx = (st.session_state.carousel_idx - 1) % len(recipes)
        st.button("◀", width='stretch', on_click=prev_carousel, key="carousel_prev")

    with col_content:
        current_recipes = []
        for i in range(TILES_PER_ROW):
            idx = (st.session_state.carousel_idx + i) % len(recipes)
            current_recipes.append(recipes[idx])
        
        card_cols = st.columns(len(current_recipes))
        
        for col, recipe in zip(card_cols, current_recipes):
            rid = recipe.get("recipe_id")
            with col:
                with st.container(border=True):
                    title = recipe.get("recipe_title", "Unknown Title")
                    display_recipe_image(title, key_suffix=f"home_{rid}")
                    
                    max_chars_per_line = 12
                    estimated_lines = len(textwrap.wrap(title, width=max_chars_per_line)) or 1
                    st.subheader(title)
                    
                    max_title_lines = 4
                    pad_lines = max(0, max_title_lines - estimated_lines)
                    for _ in range(pad_lines):
                        st.write(f"\n")
                        
                    st.write(f"⏱️ **{recipe.get('est_prep_time_min', 0)} mins**")
                    st.write("")
                    
                    st.button(
                        "View Recipe", 
                        key=f"btn_{rid}", 
                        use_container_width=True,
                        on_click=switch_page,
                        args=("Recipe Details", rid, lambda r=rid: mark_recipe_seen(r))
                    )

    with col_next:
        def next_carousel():
            st.session_state.carousel_idx = (st.session_state.carousel_idx + 1) % len(recipes)
        st.button("▶", width='stretch', on_click=next_carousel, key="carousel_next")
