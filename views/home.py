import streamlit as st
import textwrap
import os
from helpers.switch_page import switch_page
from helpers.db import search_recipes, get_recipe_by_id
from helpers.image_helper import display_recipe_image
from helpers.supabase_client import get_cooked_recipes
from helpers.recommendation_helper import get_recommended_recipes
from helpers.nutrition_helper import get_past_7_days_nutrition, draw_nutrition_radar, get_recipe_nutrition

def show_title():
    return "Home"

def show():
    # Cache Supabase call for this single execution
    cooked_recipes = get_cooked_recipes()
    current_guide_id = st.session_state.get("current_recipie_guide")

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
                    
                    if st.button("👨‍🍳 Continue Cooking", key="continue_cooking", use_container_width=True):
                        st.session_state.selected_recipe = last_cooked_id
                        switch_page("Guide")
                    if st.button("View Recipe Details", key="view_details", use_container_width=True):
                        st.session_state.selected_recipe = last_cooked_id
                        switch_page("Recipe Details")
            else:
                st.subheader("Continue where you left off:")
                last_cooked = get_recipe_by_id(current_guide_id)
                if last_cooked:
                    title = last_cooked.get('recipe_title', 'Unknown Title')
                    display_recipe_image(title, key_suffix="current_guide")
                    st.write(f"**{title}**")
                    if st.button("👨‍🍳 Continue Cooking", key="continue_cooking", use_container_width=True):
                        switch_page("Guide")
                    if st.button("View Recipe Details", key="view_details", use_container_width=True):
                        st.session_state.selected_recipe = current_guide_id
                        switch_page("Recipe Details")

    with graph:
        st.subheader("Your NutriRadar")
        with st.container(border=True):
            with st.spinner("Loading nutrition info..."):
                nut_info = get_past_7_days_nutrition()
                fig = draw_nutrition_radar(nut_info["totals"])
                st.plotly_chart(fig, use_container_width=True)

    # 1. Load Recommendations (Cached)
    recipes = get_recommended_recipes(limit=12)
    if not recipes:
        recipes = search_recipes("", limit=12)

    if "carousel_idx" not in st.session_state:
        st.session_state.carousel_idx = 0

    st.divider()
    st.subheader("Recommended Recipes")
    TILES_PER_ROW = 4

    col_prev, col_content, col_next = st.columns([1, 15, 1], vertical_alignment="center")

    with col_prev:
        if st.button("◀", width='stretch'):
            st.session_state.carousel_idx = (st.session_state.carousel_idx - 1) % len(recipes)
            st.rerun()

    with col_content:
        current_recipes = []
        for i in range(TILES_PER_ROW):
            idx = (st.session_state.carousel_idx + i) % len(recipes)
            current_recipes.append(recipes[idx])
        
        card_cols = st.columns(len(current_recipes))
        
        for col, recipe in zip(card_cols, current_recipes):
            with col:
                with st.container(border=True):
                    title = recipe.get("recipe_title", "Unknown Title")
                    display_recipe_image(title, key_suffix=f"home_{recipe['recipe_id']}")
                    
                    max_chars_per_line = 12
                    estimated_lines = len(textwrap.wrap(title, width=max_chars_per_line)) or 1
                    st.subheader(title)
                    
                    # NOTE: Removed direct get_recipe_nutrition(recipe['recipe_id']) here
                    # To avoid excessive DB hits in the loop. 
                    # Nutrition is loaded in Recipe Details anyway.
                    
                    max_title_lines = 4
                    pad_lines = max(0, max_title_lines - estimated_lines)
                    for _ in range(pad_lines):
                        st.write(f"\n")
                        
                    st.write(f"⏱️ **{recipe.get('est_prep_time_min', 0)} mins**")
                    st.write("")
                    
                    if st.button("👨‍🍳 Cook", key=f"btn_{recipe.get('recipe_id')}", use_container_width=True):
                        st.session_state.selected_recipe = recipe.get("recipe_id")
                        switch_page("Recipe Details")

    with col_next:
        if st.button("▶", width='stretch'):
            st.session_state.carousel_idx = (st.session_state.carousel_idx + 1) % len(recipes)
            st.rerun()
