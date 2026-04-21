
import requests
import streamlit as st
import random
from collections import deque

APP_NAME_TRACKING = "?utm_source=MyRecipeApp&utm_medium=referral"

@st.cache_data(ttl=86400)
def _fetch_unsplash_results(query: str):
    search_query = f"{query} food"
    url = "https://api.unsplash.com/search/photos"
    
    def fetch(q):
        params = {
            "query": q,
            "per_page": 30,
            "orientation": "landscape",
            "client_id": st.secrets["UNSPLASH_ACCESS_KEY"]
        }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json().get("results", [])
        except requests.exceptions.RequestException:
            return []
            
    results = fetch(search_query)
    if not results:
        # Fallback to broader query if specific query fails (first 2-3 words)
        short_query = " ".join(query.split()[:3]) + " food"
        results = fetch(short_query)
        
    return results

def get_unique_recipe_image_data(query: str):
    if "recent_image_history" not in st.session_state:
        st.session_state.recent_image_history = deque(maxlen=50)

    if "recipe_image_mapping" not in st.session_state:
        st.session_state.recipe_image_mapping = {}

    if query in st.session_state.recipe_image_mapping:
        return st.session_state.recipe_image_mapping[query]

    fallback_data = {
        "url": "https://placehold.co/800x600/e2e8f0/808080.png?text=Image+Unavailable",
        "is_unsplash": False
    }
    
    if not query:
        return fallback_data

    results = _fetch_unsplash_results(query)
    
    if not results:
        return fallback_data
        
    valid_images = [img for img in results if img["urls"]["regular"] not in st.session_state.recent_image_history]
    
    if valid_images:
        chosen_img = random.choice(valid_images)
    else:
        # If all exhausted, just pick random so it doesn't visibly look identical sequentially
        chosen_img = random.choice(results[:10])  # limit to top 10 to maintain relevance
        
    final_url = chosen_img["urls"]["regular"]
    st.session_state.recent_image_history.append(final_url)
    
    photographer_name = chosen_img["user"]["name"]
    photographer_link = chosen_img["user"]["links"]["html"] + APP_NAME_TRACKING
    
    download_location = chosen_img["links"]["download_location"]
    
    final_data = {
        "url": final_url,
        "photographer_name": photographer_name,
        "photographer_link": photographer_link,
        "download_location": download_location,
        "is_unsplash": True
    }
    
    st.session_state.recipe_image_mapping[query] = final_data
    return final_data

def trigger_unsplash_download(download_endpoint: str):
    try:
        params = {"client_id": st.secrets["UNSPLASH_ACCESS_KEY"]}
        requests.get(download_endpoint, params=params)
    except Exception:
        pass

def display_recipe_image(query: str, key_suffix: str = "", use_container_width=True):
    image_data = get_unique_recipe_image_data(query)
    
    st.image(image_data["url"], use_container_width=use_container_width)
    
    if image_data.get("is_unsplash"):
        download_marker_key = f"downloaded_{image_data['url']}_{key_suffix}"
        if download_marker_key not in st.session_state:
            st.session_state[download_marker_key] = True
            trigger_unsplash_download(image_data["download_location"])
            
        photographer_link = image_data['photographer_link']
        photographer_name = image_data['photographer_name']
        unsplash_link = "https://unsplash.com/" + APP_NAME_TRACKING
        
        attribution = f"<p style='text-align: center; color: gray; font-size: x-small; margin-top: -10px; margin-bottom: 10px;'>Photo by <a href='{photographer_link}' target='_blank'>{photographer_name}</a> on <a href='{unsplash_link}' target='_blank'>Unsplash</a></p>"
        st.markdown(attribution, unsafe_allow_html=True)

