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
from helpers.nutrition_helper import get_recipe_nutrition
from helpers.supabase_client import get_profile, get_vault_secrets

# Camera paths used by the Streamlit page and the separate Continuity Camera helper.
# The small flag files let both processes communicate without needing a server.
CAPTURE_PATH  = Path(__file__).parent.parent / "data" / "iphone_capture.jpg"
HELPER_SCRIPT = Path(__file__).parent.parent / "helpers" / "continuity_camera_helper.py"
READY_FLAG    = Path(__file__).parent.parent / "data" / ".cam_ready"
TRIGGER_FLAG  = Path(__file__).parent.parent / "data" / ".cam_trigger"
PID_FILE      = Path(__file__).parent.parent / "data" / ".cam_pid"



def process_and_search_recipes(image_bytes, mime_type="image/jpeg", img_hash=None):
    # The image hash prevents Gemini from re-analyzing the same uploaded/captured
    # image on every Streamlit rerun.
    if st.session_state.get("last_image_hash") != img_hash:
        with st.spinner("Analyzing ingredients using Gemini 2.5 Flash..."):
            
            # Fetching keys from Vault first keeps deployed credentials centralized,
            # while Streamlit secrets remain useful for local development.
            vault = get_vault_secrets()
            api_key_primary = vault.get("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY")
            api_key_secondary = vault.get("GEMINI_API_KEY_SECONDARY") or st.secrets.get("GEMINI_API_KEY_SECONDARY")

            if not api_key_primary:
                st.error("Gemini API Key missing.")
                return

            # Trying the primary key first keeps the normal path simple.
            success, result_text, error_msg = call_gemini_api(image_bytes, mime_type, api_key_primary)
            
            # Falling back to the secondary key helps when the primary key hits a
            # quota/rate limit during testing or demonstrations.
            if not success and api_key_secondary:
                st.info("🔄 Primary API key limit reached, switching to secondary key...")
                success, result_text, error_msg = call_gemini_api(image_bytes, mime_type, api_key_secondary)

            if not success:
                st.error(f"Error communicating with Gemini API: {error_msg}")
                return

            # Gemini is asked for JSON, but extracting the object makes parsing
            # safer if the model returns extra text around it.
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                result_text = json_match.group(0)
            
            try:
                data = json.loads(result_text)
                ingredients_list = [ing.strip().lower() for ing in data.get('ingredients', []) if ing.strip()]
            except (json.JSONDecodeError, TypeError):
                # If JSON parsing fails, splitting comma-separated text still salvages
                # simple ingredient lists instead of losing the scan result completely.
                ingredients_list = [ing.strip().lower() for ing in result_text.split(',') if len(ing.strip()) < 30]
            
            # Storing scan results in session state lets the recipe search survive reruns
            # without repeating the Gemini request.
            st.session_state["scanned_ingredients"] = ingredients_list
            st.session_state["last_image_hash"] = img_hash
            
    ingredients_list = st.session_state.get("scanned_ingredients")
    
    if ingredients_list:
        st.success(f"**Identified Ingredients:** {', '.join(ingredients_list)}")
        
        # Integrating profile preferences means scanned ingredients still respect
        # dietary restrictions and taste/speed settings.
        profile = get_profile()
        dietary = profile.get("dietary_restrictions", []) if profile else []
        cooking = profile.get("cooking_preferences", []) if profile else []
        
        if dietary or cooking:
            with st.expander("Applied Dietary & Taste Preferences"):
                if dietary: st.write(f"**Restrictions:** {', '.join(dietary)}")
                if cooking: st.write(f"**Taste/Speed:** {', '.join(cooking)}")

        recipes = search_recipes_by_ingredients(
            ingredients_list, 
            limit=12,
            dietary_prefs=dietary,
            cooking_prefs=cooking
        )
        
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
                                
                                # Triggering nutrition lookup warms the cache for recipes
                                # the user may open from the scan results.
                                get_recipe_nutrition(recipe['recipe_id'])
                                
                                st.write(f"⏱️ {recipe.get('est_prep_time_min', 0)} mins (Matches: {recipe.get('match_count', 0)})")
                                st.write("")
                                st.button(
                                    "View Recipe", 
                                    key=f"upload_btn_{recipe['recipe_id']}", 
                                    use_container_width=True,
                                    on_click=switch_page,
                                    args=("Recipe Details", recipe['recipe_id'])
                                )
        else:
            st.warning("No recipes found matching these ingredients.")

def call_gemini_api(image_bytes, mime_type, api_key):
    # Encapsulating the Gemini request keeps primary/secondary retry logic outside
    # the lower-level HTTP details.
    try:
        # Gemini expects image data as base64 inside the JSON request body.
        encoded_image = base64.b64encode(image_bytes).decode("utf-8")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        
        # The prompt asks for only ingredient names because this output feeds directly
        # into the ingredient-based recipe search.
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
        
        # The timeout prevents a slow model/network request from freezing the scan page.
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        candidates = result.get('candidates', [])
        if not candidates:
            # Returning a structured failure lets the caller show a readable Streamlit error.
            return False, "", "No candidates returned from model."
            
        content_text = candidates[0].get('content', {}).get('parts', [])[0].get('text', '')
        return True, content_text, ""
        
    except Exception as e:
        return False, "", str(e)

def show():
    st.write("Upload a picture of your ingredients or use your iPhone camera, and we'll suggest recipes you can cook!")
    
    # cam_state drives the small camera state machine: idle, starting, ready, capturing.
    if "cam_state" not in st.session_state:
        st.session_state["cam_state"] = "idle"
        st.session_state["cam_start_time"] = 0
        if CAPTURE_PATH.exists():
            try:
                # Removing an old capture avoids processing a stale image as if it
                # came from the current camera session.
                CAPTURE_PATH.unlink()
            except Exception:
                pass
        
    state = st.session_state["cam_state"]
    col1, col2 = st.columns(2)
    
    with col1:
        if state == "idle":
            # Clearing old flags resets communication with the camera helper before
            # starting a new capture flow.
            READY_FLAG.unlink(missing_ok=True)
            TRIGGER_FLAG.unlink(missing_ok=True)
            
            def start_cam():
                # Starting the helper as a subprocess keeps macOS camera handling out
                # of the main Streamlit process.
                proc = subprocess.Popen(
                    [sys.executable, str(HELPER_SCRIPT),
                     str(CAPTURE_PATH), str(READY_FLAG), str(TRIGGER_FLAG)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                # Storing the process id is useful for debugging or future cleanup logic.
                PID_FILE.write_text(str(proc.pid))
                st.session_state["cam_state"] = "starting"
                st.session_state["cam_start_time"] = time.time()

            st.button("📷 Take Photo with iPhone Camera", use_container_width=True, on_click=start_cam)

        elif state == "starting":
            if READY_FLAG.exists():
                # The helper creates READY_FLAG once the camera stream is live.
                st.session_state["cam_state"] = "ready"
                st.rerun()
            elif time.time() - st.session_state.get("cam_start_time", 0) > 10:
                st.error("Camera failed to start within 10 seconds.")
                st.info("💡 **Troubleshooting:**\n1. Run `pip install -r requirements.txt` to install camera drivers.\n2. Ensure your Terminal/IDE has **Camera Permission** in macOS Settings.\n3. Check `data/camera_error.log` for details.")
                if st.button("Retry"):
                    st.session_state["cam_state"] = "idle"
                    st.rerun()
            else:
                # Streamlit has no continuous background UI loop, so this short wait
                # and rerun lets the page poll for readiness without user clicks.
                st.info("📱 Starting camera... (checking iPhone and Built-in)")
                time.sleep(0.5)
                st.rerun()
        elif state == "ready":
            st.success("✅ Camera is live!")
            
            def trigger_capture():
                # Creating the trigger flag tells the helper to save the next frame.
                TRIGGER_FLAG.touch()
                st.session_state["cam_state"] = "capturing"
            
            st.button("📸 Capture now!", use_container_width=True, on_click=trigger_capture)

        elif state == "capturing":
            trigger_time = 0
            if TRIGGER_FLAG.exists():
                trigger_time = TRIGGER_FLAG.stat().st_mtime
            
            # Waiting for the captured image to be newer than the trigger prevents
            # accidentally displaying an older photo from a previous attempt.
            if CAPTURE_PATH.exists() and CAPTURE_PATH.stat().st_mtime >= trigger_time:
                st.session_state["cam_state"] = "idle"
                # Cleaning up flags prepares the next capture session.
                READY_FLAG.unlink(missing_ok=True)
                TRIGGER_FLAG.unlink(missing_ok=True)
                st.rerun()
            else:
                st.info("⏳ Capturing frame...")
                time.sleep(0.5)
                st.rerun()
        st.divider()
        uploaded_file = st.file_uploader("Or choose an image...", type=["jpg", "jpeg", "png"])

    with col2:
        # These stay None until either an uploaded image or captured image is available.
        image_bytes_to_process = None
        mime_type_to_process = None
        if uploaded_file is not None:
            # Uploaded files already include their MIME type, which Gemini needs for inline data.
            st.image(uploaded_file, caption="Uploaded Image", use_container_width=True)
            image_bytes_to_process = uploaded_file.getvalue()
            mime_type_to_process = uploaded_file.type
        elif state == "idle" and CAPTURE_PATH.exists():
            try:
                st.image(str(CAPTURE_PATH), caption="Captured Image", use_container_width=True)
                # Captured camera photos are saved as JPEG by the helper script.
                with open(CAPTURE_PATH, "rb") as f:
                    image_bytes_to_process = f.read()
                mime_type_to_process = "image/jpeg"
            except Exception:
                pass
                
    st.divider()
    if image_bytes_to_process:
        import hashlib
        # Hashing the bytes identifies whether the user is still looking at the
        # same image or has uploaded/captured a new one.
        img_hash = hashlib.md5(image_bytes_to_process).hexdigest()
        process_and_search_recipes(image_bytes_to_process, mime_type_to_process, img_hash)
