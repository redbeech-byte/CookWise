import streamlit as st
import ast
from helpers.db import get_recipe_by_id
from helpers.switch_page import switch_page
from helpers.image_helper import display_recipe_image, get_unique_recipe_image_data

def show_title():
    return "Cooking Interactive Guide"

def show():
    # Use .get() defensively and check for None/empty
    recipe_id = st.session_state.get("selected_recipe")
    if recipe_id is None:
        st.warning("No recipe selected.")
        st.button("Go Home", on_click=switch_page, args=("Home",))
        return
        
    recipe = get_recipe_by_id(recipe_id)
    if not recipe:
        st.error(f"Recipe not found (ID: {recipe_id}).")
        st.button("Go Home", on_click=switch_page, args=("Home",))
        return

    # Fix typo 'recipie' -> 'recipe'
    if st.session_state.get("current_recipe_guide") != recipe_id:
        st.session_state["current_recipe_guide"] = recipe_id
        st.session_state[f"current_step_{recipe_id}"] = 0

    directions_str = recipe.get("directions", "[]")
    directions = []
    try:
        directions = ast.literal_eval(directions_str)
    except Exception:
        directions = [step.strip() for step in directions_str.split(".") if step.strip()]
        
    if not directions:
        st.warning("No directions available for this recipe.")
        return

    step_key = f"current_step_{recipe_id}"
    if step_key not in st.session_state:
        st.session_state[step_key] = 0
        
    current_step = st.session_state[step_key]

    # PRELOAD next steps to avoid "grey out" lag when clicking Next
    for i in range(current_step, min(current_step + 3, len(directions))):
        s_text = directions[i]
        s_words = [w for w in s_text.split() if len(w) > 2]
        s_query = " ".join(s_words[:4]) if s_words else recipe.get("recipe_title", "cooking")
        get_unique_recipe_image_data(s_query)
    
    st.subheader(f"👨‍🍳 {recipe.get('recipe_title', 'Recipe')}")
    progress = (current_step) / max(1, (len(directions) - 1))
    st.progress(progress, text=f"Step {current_step + 1} of {len(directions)}")
    
    st.write("")
    with st.container(border=True):
        st.title(f"Step {current_step + 1}")
        step_text = directions[current_step]
        step_words = [w for w in step_text.split() if len(w) > 2]
        search_query = " ".join(step_words[:4]) if step_words else recipe.get("recipe_title", "cooking")
        
        col_img, col_text = st.columns(2)
        with col_img:
            display_recipe_image(search_query, key_suffix=f"guide_{recipe_id}_{current_step}")
        with col_text:
            st.write(f"### {step_text}")
        
    st.write("")
    col_prev, col_spacer, col_next = st.columns([2, 5, 2])
    
    with col_prev:
        if current_step > 0:
            def prev_step():
                st.session_state[step_key] -= 1
            st.button("⬅️ Previous Step", use_container_width=True, on_click=prev_step)
        else:
            st.button("⬅️ Back to Details", use_container_width=True, on_click=switch_page, args=("Recipe Details",))
                
    with col_next:
        if current_step < len(directions) - 1:
            def next_step():
                st.session_state[step_key] += 1
            st.button("Next Step ➡️", type="primary", use_container_width=True, on_click=next_step)
        else:
            def finish_cooking():
                st.session_state[step_key] = 0
            st.button("🎉 Finish!", type="primary", use_container_width=True, on_click=switch_page, args=("Recipe Details", None, finish_cooking))
