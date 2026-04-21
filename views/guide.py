import streamlit as st
import ast
from helpers.db import get_recipe_by_id
from helpers.switch_page import switch_page
from helpers.image_helper import display_recipe_image

def show_title():
    return "Cooking Interactive Guide"

def show():
    recipe_id = st.session_state.get("selected_recipe")
    if not recipe_id:
        st.warning("No recipe selected.")
        if st.button("Go Home"):
            switch_page("Home")
        return
        
    recipe = get_recipe_by_id(recipe_id)
    if not recipe:
        st.error("Recipe not found.")
        return

    if "current_recipie_guide" not in st.session_state:
        st.session_state["current_recipie_guide"] = recipe_id
        st.session_state[f"current_step_{recipe_id}"] = 0  # Reset to step 0 when a new recipe is selected

    if st.session_state["current_recipie_guide"] != recipe_id:
        st.session_state["current_recipie_guide"] = recipe_id
        st.session_state[f"current_step_{recipe_id}"] = 0  # Reset to step 0 when a new recipe is selected
    # Parse directions
    directions_str = recipe.get("directions", "[]")
    directions = []
    try:
        directions = ast.literal_eval(directions_str)
    except Exception:
        # Fallback if it is a single big string
        directions = [step.strip() for step in directions_str.split(".") if step.strip()]
        
    if not directions:
        st.warning("No directions available for this recipe.")
        return

    # Initialize current step in session_state if not there
    step_key = f"current_step_{recipe_id}"
    if step_key not in st.session_state:
        st.session_state[step_key] = 0
        
    current_step = st.session_state[step_key]
    
    # Header
    st.subheader(f"👨‍🍳 {recipe.get('recipe_title', 'Recipe')}")
    
    # Progress bar
    progress = (current_step) / max(1, (len(directions) - 1))
    st.progress(progress, text=f"Step {current_step + 1} of {len(directions)}")
    
    # Main Step Card
    st.write("")
    with st.container(border=True):
        st.title(f"Step {current_step + 1}")
        
        # Pull a specific picture for exactly what this cooking step instructs
        step_text = directions[current_step]
        
        # Grab the first 4 long words of the step text as a generic query to Unsplash
        # (e.g. "Preheat the oven to 450 degrees" -> "Preheat oven degrees")
        step_words = [w for w in step_text.split() if len(w) > 2]
        search_query = " ".join(step_words[:4]) if step_words else recipe.get("recipe_title", "cooking")
        
        # Structure layout to picture on left, description on right
        col_img, col_text = st.columns(2)
        with col_img:
            display_recipe_image(search_query, key_suffix=f"guide_{recipe_id}_{current_step}")
        
        with col_text:
            st.write(f"### {step_text}")
        
        st.write("")
        st.write("")
        
    # Navigation Buttons
    st.write("")
    col_prev, col_spacer, col_next = st.columns([2, 5, 2])
    
    with col_prev:
        if current_step > 0:
            if st.button("⬅️ Previous Step", use_container_width=True):
                st.session_state[step_key] -= 1
                st.rerun()
        else:
            if st.button("⬅️ Back to Details", use_container_width=True):
                switch_page("Recipe Details")
                
    with col_next:
        if current_step < len(directions) - 1:
            if st.button("Next Step ➡️", type="primary", use_container_width=True):
                st.session_state[step_key] += 1
                st.rerun()
        else:
            if st.button("🎉 Finish Cooking!", type="primary", use_container_width=True):
                st.balloons()
                st.session_state[step_key] = 0 # Reset for next time
                switch_page("Recipe Details")

