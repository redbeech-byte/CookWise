import streamlit as st
from helpers.switch_page import switch_page
from helpers.db import search_recipes
from helpers.image_helper import display_recipe_image
def show_title():
        return "Search Recipes"
def show():
    
    st.space("medium")
    with st.container(border=True):

        search_bar, spacer, filter_popover = st.columns([9,1,2], vertical_alignment="bottom")

        with search_bar:
            query = st.text_input( "", placeholder="Enter ingredient, name, or keywords...",)
            
        with filter_popover:
            with st.popover("Filter", icon="🎯"):
                #range slider with upper and lower bounds for max time, difficulty (dropdown with any, easy, medium, hard), and dietary preferences (checkboxes for vegan, vegetarian, gluten-free, dairy-free, nut-free)
                min_time, max_time = st.slider("Time Range (mins)", min_value=10, max_value=240, value=(10,240), step=2)
                difficulty = st.selectbox("Difficulty", ["Any", "Easy", "Medium", "Hard"])
                
                st.write("Dietary Preferences")
                col1, col2 = st.columns(2)
                dietary_prefs = []
                with col1:
                    if st.checkbox("Vegan"): dietary_prefs.append("Vegan")
                    if st.checkbox("Vegetarian"): dietary_prefs.append("Vegetarian")
                with col2:
                    if st.checkbox("Gluten-Free"): dietary_prefs.append("Gluten-Free")
                    if st.checkbox("Dairy-Free"): dietary_prefs.append("Dairy-Free")
                    if st.checkbox("Nut-Free"): dietary_prefs.append("Nut-Free")
                    
        # When user finishes setup, we run the search with the filters!
        results = search_recipes(
            query=query, 
            limit=50, 
            max_time=max_time if max_time < 240 else None,
            min_time=min_time if min_time > 10 else None,
            difficulty=difficulty,
            dietary_prefs=dietary_prefs
        )
    
    st.subheader(f"Results ({len(results)})")
    
    from helpers.nutrition_helper import get_recipe_nutrition

    if results:
        cols_per_row = 3
        for i in range(0, len(results), cols_per_row):
            cols = st.columns(cols_per_row)
            for j in range(cols_per_row):
                if i + j < len(results):
                    recipe = results[i + j]
                    with cols[j]:
                        display_recipe_image(recipe.get('recipe_title', 'recipe'), key_suffix=str(recipe['recipe_id']))
                        st.write(f"**{recipe.get('recipe_title')}**")

                        # Pre-load the nutrition data in the background (caches in DB)
                        get_recipe_nutrition(recipe['recipe_id'])

                        st.write(f"⏱️ {recipe.get('est_prep_time_min', 0)} mins")
                        if st.button("View Recipe", key=f"search_btn_{recipe['recipe_id']}"):
                            st.session_state.selected_recipe = recipe['recipe_id']
                            switch_page("Recipe Details")
    else:
        st.info("No recipes found.")
