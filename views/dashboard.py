import streamlit as st
from project.github.CookWise.helpers.image_helper import get_unique_recipe_image_data, trigger_unsplash_download

def show_dashboard():
    st.title("Recipe Dashboard")
    
    recipe_name = "Spicy Basil Chicken"
    st.subheader(recipe_name)
    
    # Fetch unique image data for the given recipe query
    image_data = get_unique_recipe_image_data(recipe_name)
    
    # Display the image using the provided URL
    st.image(image_data["url"], use_container_width=True)
    
    # Check if the image came from Unsplash to show attribution and trigger download count
    if image_data.get("is_unsplash"):
        
        # Trigger download endpoint (only once per session for this image URL)
        download_marker_key = f"downloaded_{image_data['url']}"
        if download_marker_key not in st.session_state:
            st.session_state[download_marker_key] = True
            trigger_unsplash_download(image_data["download_location"])
            
        # Parse attribution variables
        photographer_link = image_data['photographer_link']
        photographer_name = image_data['photographer_name']
        unsplash_link = "https://unsplash.com/?utm_source=MyRecipeApp&utm_medium=referral"
        
        # Render HTML attribution string
        attribution = f"<p style='text-align: center; color: gray; font-size: small;'>Photo by <a href='{photographer_link}' target='_blank'>{photographer_name}</a> on <a href='{unsplash_link}' target='_blank'>Unsplash</a></p>"
        st.markdown(attribution, unsafe_allow_html=True)

if __name__ == "__main__":
    show_dashboard()
