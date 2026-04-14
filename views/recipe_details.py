import streamlit as st
import ast
from project.github.CookWise.helpers.db import get_recipe_by_id, get_ingredients_for_recipe
from project.github.CookWise.helpers.image_helper import display_recipe_image

def show():
    recipe_id = st.session_state.get('selected_recipe', None)

    if recipe_id is None:
        st.warning("No recipe selected.")
        return
    
    recipe = get_recipe_by_id(recipe_id)
    if not recipe:
        st.error("Recipe not found in the database.")
        return
        
    recipe_title = recipe.get("recipe_title", "Unknown Recipe")
    st.title(recipe_title)
    
    display_recipe_image(recipe_title, key_suffix=f"details_{recipe_id}")
    
    st.write(f"**Description:** {recipe.get('description', '')}")
    st.write(f"⏱️ **Prep time:** {recipe.get('est_prep_time_min', 0)} mins | **Cook time:** {recipe.get('est_cook_time_min', 0)} mins")
    
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
