import streamlit as st
import requests
import base64
import subprocess
import sys
import time
import json
import re
from pathlib import Path

from helpers.db import search_recipes_by_ingredients
from helpers.switch_page import switch_page
from helpers.image_helper import display_recipe_image

# Load API keys
GEMINI_API_KEY_PRIMARY = st.secrets["GEMINI_API_KEY"]
GEMINI_API_KEY_SECONDARY = st.secrets.get("GEMINI_API_KEY_SECONDARY")

CAPTURE_PATH  = Path(__file__).parent.parent / "data" / "iphone_capture.jpg"
HELPER_SCRIPT = Path(__file__).parent.parent / "helpers" / "continuity_camera_helper.py"
READY_FLAG    = Path(__file__).parent.parent / "data" / ".cam_ready"
TRIGGER_FLAG  = Path(__file__).parent.parent / "data" / ".cam_trigger"
PID_FILE      = Path(__file__).parent.parent / "data" / ".cam_pid"

def show_title():
    return "FridgeScan"

def process_and_search_recipes(image_bytes, mime_type="image/jpeg", img_hash=None):
    if st.session_state.get("last_image_hash") != img_hash:
        with st.spinner("Analyzing ingredients using Gemini 2.5 Flash..."):
            
            # Primary attempt
            success, result_text, error_msg = call_gemini_api(image_bytes, mime_type, GEMINI_API_KEY_PRIMARY)
            
            # Secondary fallback if primary fails (e.g. 429 Limit reached)
            if not success and GEMINI_API_KEY_SECONDARY:
                st.info("🔄 Primary API key limit reached, switching to secondary key...")
                success, result_text, error_msg = call_gemini_api(image_bytes, mime_type, GEMINI_API_KEY_SECONDARY)

            if not success:
                st.error(f"Error communicating with Gemini API: {error_msg}")
                return

            # Extract and parse JSON
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                result_text = json_match.group(0)
            
            try:
                data = json.loads(result_text)
                ingredients_list = [ing.strip().lower() for ing in data.get('ingredients', []) if ing.strip()]
            except (json.JSONDecodeError, TypeError):
                ingredients_list = [ing.strip().lower() for ing in result_text.split(',') if len(ing.strip()) < 30]
            
            st.session_state["scanned_ingredients"] = ingredients_list
            st.session_state["last_image_hash"] = img_hash
            
    ingredients_list = st.session_state.get("scanned_ingredients")
    
    from helpers.nutrition_helper import get_recipe_nutrition

    if ingredients_list:
        st.success(f"**Identified Ingredients:** {', '.join(ingredients_list)}")
        
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
                            with st.container(border=True, height=450):
                                display_recipe_image(recipe.get('recipe_title', 'recipe'), key_suffix=str(recipe['recipe_id']) + '_up')
                                title = recipe.get('recipe_title', 'Unknown Title')
                                if len(title) > 55:
                                    title = title[:52] + "..."
                                st.write(f"**{title}**")
                                get_recipe_nutrition(recipe['recipe_id'])
                                st.write(f"⏱️ {recipe.get('est_prep_time_min', 0)} mins (Matches: {recipe.get('match_count', 0)})")
                                st.write("")
                                st.button(
                                    "👨‍🍳 Cook", 
                                    key=f"upload_btn_{recipe['recipe_id']}", 
                                    use_container_width=True,
                                    on_click=switch_page,
                                    args=("Recipe Details", recipe['recipe_id'])
                                )
        else:
            st.warning("No recipes found matching these ingredients.")

def call_gemini_api(image_bytes, mime_type, api_key):
    """Encapsulated API call logic for primary/secondary retry."""
    try:
        encoded_image = base64.b64encode(image_bytes).decode("utf-8")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        
        payload = {
            "contents": [{
                "parts": [
                    {"text": "Identify the cooking ingredients in this image. Return a JSON object with a single key 'ingredients' containing a list of strings. DO NOT include any 'thinking', 'reasoning', or preamble. Return ONLY the JSON block."},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": encoded_image
                        }
                    }
                ]
            }],
            "generationConfig": {
                "response_mime_type": "application/json"
            }
        }
        
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        candidates = result.get('candidates', [])
        if not candidates:
            return False, "", "No candidates returned from model."
            
        content_text = candidates[0].get('content', {}).get('parts', [])[0].get('text', '')
        return True, content_text, ""
        
    except Exception as e:
        return False, "", str(e)

def show():
    st.write("Upload a picture of your ingredients or use your iPhone camera, and we'll suggest recipes you can cook!")
    
    if "cam_state" not in st.session_state:
        st.session_state["cam_state"] = "idle"
        if CAPTURE_PATH.exists():
            try:
                CAPTURE_PATH.unlink()
            except Exception:
                pass
        
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
                st.info("📱 Starting iPhone camera...")
                time.sleep(0.4)
                st.rerun()
        elif state == "ready":
            st.success("✅ iPhone is live!")
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
        st.divider()
        uploaded_file = st.file_uploader("Or choose an image...", type=["jpg", "jpeg", "png"])

    with col2:
        image_bytes_to_process = None
        mime_type_to_process = None
        if uploaded_file is not None:
            st.image(uploaded_file, caption="Uploaded Image", use_container_width=True)
            image_bytes_to_process = uploaded_file.getvalue()
            mime_type_to_process = uploaded_file.type
        elif state == "idle" and CAPTURE_PATH.exists():
            try:
                st.image(str(CAPTURE_PATH), caption="Captured Image", use_container_width=True)
                with open(CAPTURE_PATH, "rb") as f:
                    image_bytes_to_process = f.read()
                mime_type_to_process = "image/jpeg"
            except Exception:
                pass
                
    st.divider()
    if image_bytes_to_process:
        import hashlib
        img_hash = hashlib.md5(image_bytes_to_process).hexdigest()
        process_and_search_recipes(image_bytes_to_process, mime_type_to_process, img_hash)
