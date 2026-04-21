from views import guide, recipe_details, search, scan
import streamlit as st

from helpers.switch_page import switch_page
from helpers.db import search_recipes
from helpers.image_helper import display_recipe_image

import os
import textwrap
def show_title():
    return "Home"
# We removed set_page_config since it throws an error if called twice across pages.
def show():

    st.write("Welcome to your recipe dashboard. Here you will see your saved recipes and recommendations.")


    navigation,spacer, graph = st.columns([2,1,5])

    with navigation: #using buttons to navigate to the other pages
        with st.container():
            st.subheader("Menu")
            if st.button("Search Recipes"):
                switch_page("Search")
            if st.button("Upload Ingredients"):
                switch_page("Upload")


    with graph:
        st.subheader("")
        with st.container(border=True):
            from helpers.nutrition_helper import get_past_7_days_nutrition, draw_nutrition_radar
            with st.spinner("Loading nutrition info..."):
                nut_info = get_past_7_days_nutrition()
                fig = draw_nutrition_radar(nut_info["totals"])
                st.plotly_chart(fig, use_container_width=True)

    # Database recipes
    recipes = search_recipes("", limit=6)
    if not recipes:
        st.warning("No recipes in the database.")
        return

    # 2. Setup Carousel State
    # This remembers which recipes we are currently looking at
    if "carousel_idx" not in st.session_state:
        st.session_state.carousel_idx = 0

    st.divider()
    st.subheader("Recommended Recipes")
    TILES_PER_ROW = 4

    # 3. Create the Layout: Left Arrow, Content, Right Arrow
    col_prev, col_content, col_next = st.columns([1, 15, 1], vertical_alignment="center")

    # --- LEFT ARROW ---
    with col_prev:
        if st.button("◀", width='stretch'):
            st.session_state.carousel_idx = (st.session_state.carousel_idx - 1) % len(recipes)
            st.rerun()

    # --- CENTER CONTENT (THE ROW) ---
    with col_content:
        # Get the next TILES_PER_ROW recipes, wrapping around if necessary
        current_recipes = []
        for i in range(TILES_PER_ROW):
            idx = (st.session_state.carousel_idx + i) % len(recipes)
            current_recipes.append(recipes[idx])
        
        # Create exactly the number of columns we need for this view
        card_cols = st.columns(len(current_recipes))
        
        for col, recipe in zip(card_cols, current_recipes):
            with col:
                with st.container(border=True):
                    display_recipe_image(recipe.get('recipe_title', 'recipe'), key_suffix=f"home_{recipe['recipe_id']}")
                    
                    title = recipe.get("recipe_title", "Unknown Title")
                    
                    # Estimate the number of lines the title will span based on word wrap logic
                    max_chars_per_line = 12 # approximate chars before Streamlit wraps a subheader
                    estimated_lines = len(textwrap.wrap(title, width=max_chars_per_line)) or 1
                    
                    st.subheader(title)
                    
                    # Assume a maximum height of 4 lines. Add empty lines for padding.
                    max_title_lines = 7
                    pad_lines = max(0, max_title_lines - estimated_lines)
                    for _ in range(pad_lines):
                        st.write(f"\n")
                        
                    st.write(f"⏱️ **{recipe.get('est_prep_time_min', 0)} mins**")
                    
                    # Push the button cleanly to the bottom
                    st.write("")
                    
                    if st.button("👨‍🍳 Cook", key=f"btn_{recipe.get('recipe_id')}", use_container_width=True):
                        st.session_state.selected_recipe = recipe.get("recipe_id")
                        switch_page("Recipe Details")

    # --- RIGHT ARROW ---
    with col_next:
        if st.button("▶", width='stretch'):
            st.session_state.carousel_idx = (st.session_state.carousel_idx + 1) % len(recipes)
            st.rerun()