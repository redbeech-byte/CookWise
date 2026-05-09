
import requests
import streamlit as st
import random
from collections import deque
from helpers.supabase_client import get_vault_secrets

# Unsplash requires attribution links to identify the app that sent the traffic.
APP_NAME_TRACKING = "?utm_source=MyRecipeApp&utm_medium=referral"

@st.cache_data(ttl=86400)
def _fetch_unsplash_results(query: str):
    # Searching with "food" added helps Unsplash return recipe-style images instead
    # of unrelated images that only match the recipe name loosely.
    search_query = f"{query} food"
    url = "https://api.unsplash.com/search/photos"
    
    # Fetching the API key from Vault first keeps the deployed app configurable,
    # while the Streamlit secret fallback keeps local development possible.
    vault = get_vault_secrets()
    access_key = vault.get("UNSPLASH_ACCESS_KEY") or st.secrets.get("UNSPLASH_ACCESS_KEY")
    
    if not access_key:
        # Returning an empty list lets the caller use the placeholder image instead
        # of breaking the page when the Unsplash key is missing.
        return []

    def fetch(q):
        params = {
            "query": q,
            "per_page": 30,
            "orientation": "landscape",
            "client_id": access_key
        }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json().get("results", [])
        except requests.exceptions.RequestException:
            # Network errors or API failures return no results so the UI can fall
            # back cleanly instead of showing a traceback.
            return []
            
    results = fetch(search_query)
    if not results:
        # Falling back to the first few words makes long recipe titles less strict.
        # This helps when Unsplash has no exact match for the full recipe name.
        short_query = " ".join(query.split()[:3]) + " food"
        results = fetch(short_query)
        
    return results

def get_unique_recipe_image_data(query: str):
    # Keeping a short history prevents recipe cards from repeatedly showing the
    # exact same image during one Streamlit session.
    if "recent_image_history" not in st.session_state:
        st.session_state.recent_image_history = deque(maxlen=50)

    # Mapping each query to one chosen image keeps the same recipe visually stable
    # across reruns instead of changing images every time Streamlit refreshes.
    if "recipe_image_mapping" not in st.session_state:
        st.session_state.recipe_image_mapping = {}

    if query in st.session_state.recipe_image_mapping:
        return st.session_state.recipe_image_mapping[query]

    # Placeholder data keeps the layout intact when a recipe has no query, the API
    # key is missing, or Unsplash returns no usable image.
    fallback_data = {
        "url": "https://placehold.co/800x600/e2e8f0/808080.png?text=Image+Unavailable",
        "is_unsplash": False
    }
    
    if not query:
        return fallback_data

    results = _fetch_unsplash_results(query)
    
    if not results:
        return fallback_data
        
    # Prefer images that have not appeared recently, so pages with many recipe
    # cards feel more varied.
    valid_images = [img for img in results if img["urls"]["regular"] not in st.session_state.recent_image_history]
    
    if valid_images:
        chosen_img = random.choice(valid_images)
    else:
        # If all recent options are exhausted, choosing from the top results still
        # keeps the image relevant while avoiding a completely deterministic repeat.
        chosen_img = random.choice(results[:10])
        
    final_url = chosen_img["urls"]["regular"]
    st.session_state.recent_image_history.append(final_url)
    
    # Saving attribution details is necessary because Unsplash photos must credit
    # the photographer and link back to Unsplash.
    photographer_name = chosen_img["user"]["name"]
    photographer_link = chosen_img["user"]["links"]["html"] + APP_NAME_TRACKING
    
    # Unsplash asks apps to trigger the download endpoint when an image is used,
    # which helps their platform track image usage correctly.
    download_location = chosen_img["links"]["download_location"]
    
    final_data = {
        "url": final_url,
        "photographer_name": photographer_name,
        "photographer_link": photographer_link,
        "download_location": download_location,
        "is_unsplash": True
    }
    
    # Store the chosen image for this query so the same recipe does not change
    # image during normal Streamlit reruns.
    st.session_state.recipe_image_mapping[query] = final_data
    return final_data

def trigger_unsplash_download(download_endpoint: str):
    # Triggering the Unsplash download endpoint records that the app displayed
    # the image. This is separate from simply showing the image URL.
    try:
        # Fetching the key from Vault first, with Streamlit secrets as local fallback.
        vault = get_vault_secrets()
        access_key = vault.get("UNSPLASH_ACCESS_KEY") or st.secrets.get("UNSPLASH_ACCESS_KEY")
        if not access_key:
            return
            
        params = {"client_id": access_key}
        requests.get(download_endpoint, params=params)
    except Exception:
        # Failing to record the download should not stop the recipe page from loading.
        pass

def display_recipe_image(query: str, key_suffix: str = "", use_container_width=True):
    # Fetching image data separately keeps the display function focused on Streamlit
    # rendering and attribution.
    image_data = get_unique_recipe_image_data(query)
    
    st.image(image_data["url"], use_container_width=use_container_width)
    
    if image_data.get("is_unsplash"):
        # The marker prevents repeated download tracking calls for the same rendered
        # image during Streamlit reruns.
        download_marker_key = f"downloaded_{image_data['url']}_{key_suffix}"
        if download_marker_key not in st.session_state:
            st.session_state[download_marker_key] = True
            trigger_unsplash_download(image_data["download_location"])
        
        photographer_link = image_data['photographer_link']
        photographer_name = image_data['photographer_name']
        unsplash_link = "https://unsplash.com/" + APP_NAME_TRACKING
        
        # attribution for the images is a requirement by unsplash,
        attribution = f"<p style='text-align: center; color: gray; font-size: x-small; margin-top: -10px; margin-bottom: 10px;'>Photo by <a href='{photographer_link}' target='_blank'>{photographer_name}</a> on <a href='{unsplash_link}' target='_blank'>Unsplash</a></p>"
        st.markdown(attribution, unsafe_allow_html=True)

