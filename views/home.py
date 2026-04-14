from project.github.CookWise.views import guide, recipe_details, search
import streamlit as st
from project.github.CookWise.views import upload
from project.github.CookWise.helpers.switch_page import switch_page
from project.github.CookWise.helpers.db import search_recipes
from project.github.CookWise.helpers.image_helper import display_recipe_image

# We removed set_page_config since it throws an error if called twice across pages.
def show():
    st.title("Home")
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
            #on the top left there should be a graph which is for now a picture placeholder
            st.image("project/personal/recipe_app/pictures/graph_placeholder.png", caption="Your Cooking Activity")

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
    TILES_PER_ROW = 3

    # 3. Create the Layout: Left Arrow, Content, Right Arrow
    col_prev, col_content, col_next = st.columns([1, 8, 1], vertical_alignment="center")

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
                    st.subheader(recipe.get("recipe_title", "Unknown Title"))
                    st.caption(f"⏱️ {recipe.get('est_prep_time_min', 0)} mins")
                    if st.button("Cook", key=f"btn_{recipe.get('recipe_id')}", width='stretch'):
                        st.session_state.selected_recipe = recipe.get("recipe_id")
                        switch_page("Recipe Details")

    # --- RIGHT ARROW ---
    with col_next:
        if st.button("▶", width='stretch'):
            st.session_state.carousel_idx = (st.session_state.carousel_idx + 1) % len(recipes)
            st.rerun()