import streamlit as st
import requests
import base64
import subprocess
import sys
import time
from pathlib import Path

from helpers.db import search_recipes_by_ingredients
from helpers.switch_page import switch_page
from helpers.image_helper import display_recipe_image

GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

CAPTURE_PATH  = Path(__file__).parent.parent / "data" / "iphone_capture.jpg"
HELPER_SCRIPT = Path(__file__).parent.parent / "helpers" / "continuity_camera_helper.py"
READY_FLAG    = Path(__file__).parent.parent / "data" / ".cam_ready"
TRIGGER_FLAG  = Path(__file__).parent.parent / "data" / ".cam_trigger"
PID_FILE      = Path(__file__).parent.parent / "data" / ".cam_pid"

def process_and_search_recipes(image_bytes, mime_type="image/jpeg"):
    with st.spinner("Analyzing ingredients using Gemini..."):
        try:
            # Convert image to base64
            encoded_image = base64.b64encode(image_bytes).decode("utf-8")
            
            # Prepare the Gemini API request
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
            
            payload = {
                "contents": [{
                    "parts": [
                        {"text": "Identify the cooking ingredients in this image. Return ONLY a comma-separated list of the ingredient names. Do not include any other text, markdown, or explanations."},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": encoded_image
                            }
                        }
                    ]
                }]
            }
            
            response = requests.post(url, json=payload)
            response.raise_for_status()
            
            result = response.json()
            candidates = result.get('candidates', [])
            
            if not candidates:
                st.error("No ingredients found in the image. Please try another one.")
                return
                
            content_text = candidates[0].get('content', {}).get('parts', [])[0].get('text', '')
            ingredients_list = [ing.strip().lower() for ing in content_text.split(',') if ing.strip()]
            
            st.success(f"**Identified Ingredients:** {', '.join(ingredients_list)}")
            
            # Search recipes based on the ingredients
            recipes = search_recipes_by_ingredients(ingredients_list, limit=12)
            
            if recipes:
                st.subheader(f"Matching Recipes ({len(recipes)})")
                cols_per_row = 3
                for i in range(0, len(recipes), cols_per_row):
                    cols = st.columns(cols_per_row)
                    for j in range(cols_per_row):
                        if i + j < len(recipes):
                            recipe = recipes[i + j]
                            with cols[j]:
                                display_recipe_image(recipe.get('recipe_title', 'recipe'), key_suffix=str(recipe['recipe_id']) + '_up')
                                st.write(f"**{recipe.get('recipe_title')}**")
                                st.write(f"⏱️ {recipe.get('est_prep_time_min', 0)} mins (Matches: {recipe.get('match_count', 0)})")
                                if st.button("View Recipe", key=f"upload_btn_{recipe['recipe_id']}"):
                                    st.session_state.selected_recipe = recipe['recipe_id']
                                    switch_page("Recipe Details")
            else:
                st.warning("No recipes found matching these ingredients.")
                
        except Exception as e:
            st.error(f"Error communicating with Gemini API: {str(e)}")

def show():
    st.title("Upload Ingredients")
    st.write("Upload a picture of your ingredients or use your iPhone camera, and we'll suggest recipes you can cook!")
    
    if "cam_state" not in st.session_state:
        st.session_state["cam_state"] = "idle"
        
    state = st.session_state["cam_state"]

    col1, col2 = st.columns(2)
    
    with col1:
        if state == "idle":
            READY_FLAG.unlink(missing_ok=True)
            TRIGGER_FLAG.unlink(missing_ok=True)

            if st.button("📷 Take Photo with iPhone Camera", use_container_width=True):
                proc = subprocess.Popen(
                    [sys.executable, str(HELPER_SCRIPT),
                     str(CAPTURE_PATH), str(READY_FLAG), str(TRIGGER_FLAG)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                PID_FILE.write_text(str(proc.pid))
                st.session_state["cam_state"] = "starting"
                st.rerun()

        elif state == "starting":
            if READY_FLAG.exists():
                st.session_state["cam_state"] = "ready"
                st.rerun()
            else:
                st.info("📱 Starting iPhone camera... (check your phone)")
                time.sleep(0.4)
                st.rerun()

        elif state == "ready":
            st.success("✅ iPhone is live! Point it at your ingredients.")
            if st.button("📸 Capture now!", use_container_width=True):
                TRIGGER_FLAG.touch()
                st.session_state["cam_state"] = "capturing"
                st.rerun()

        elif state == "capturing":
            trigger_time = 0
            if TRIGGER_FLAG.exists():
                trigger_time = TRIGGER_FLAG.stat().st_mtime
                
            if CAPTURE_PATH.exists() and CAPTURE_PATH.stat().st_mtime >= trigger_time and CAPTURE_PATH.stat().st_mtime > time.time() - 10:
                st.session_state["cam_state"] = "idle"
                READY_FLAG.unlink(missing_ok=True)
                TRIGGER_FLAG.unlink(missing_ok=True)
                st.rerun()
            else:
                st.info("⏳ Capturing frame...")
                time.sleep(0.4)
                st.rerun()
                
    with col2:
        uploaded_file = st.file_uploader("Or choose an image...", type=["jpg", "jpeg", "png"])
    
    st.divider()

    # Priority to immediately uploaded file, then standard capture
    if uploaded_file is not None:
        st.image(uploaded_file, caption="Uploaded Image", use_container_width=True)
        if st.button("Find Recipes from Upload"):
            process_and_search_recipes(uploaded_file.getvalue(), uploaded_file.type)
            
    elif state == "idle" and CAPTURE_PATH.exists():
        try:
            st.image(str(CAPTURE_PATH), caption="Captured Image", use_container_width=True)
            if st.button("Find Recipes from Camera Capture"):
                # Pass the saved image file
                with open(CAPTURE_PATH, "rb") as f:
                    image_bytes = f.read()
                process_and_search_recipes(image_bytes, "image/jpeg")
        except Exception:
            pass

