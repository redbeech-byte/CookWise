import streamlit as st
from project.github.CookWise.helpers.switch_page import switch_page
from project.github.CookWise.helpers.db import search_recipes
from project.github.CookWise.helpers.image_helper import display_recipe_image

def show():
    st.title("Search Recipes")
    query = st.text_input("Enter ingredient, name, or keywords...", "")
    
    results = search_recipes(query)
    
    st.subheader(f"Results ({len(results)})")
    
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
                        st.write(f"⏱️ {recipe.get('est_prep_time_min', 0)} mins")
                        if st.button("View Recipe", key=f"search_btn_{recipe['recipe_id']}"):
                            st.session_state.selected_recipe = recipe['recipe_id']
                            switch_page("Recipe Details")
    else:
        st.info("No recipes found.")
