from project.github.CookWise.views import guide, home, recipe_details, search
import streamlit as st
# Consolidated imports
from project.github.CookWise.views import upload
from project.github.CookWise.helpers.switch_page import switch_page
import time

st.set_page_config(page_title="Recipe App", layout="wide")

def initialize_state():
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "Home"
    if 'selected_recipe' not in st.session_state:
        st.session_state.selected_recipe = None

def login_screen():
    # Squeezes the login box into the middle of the screen
    spacer_left, content, spacer_right = st.columns([1, 2, 1])
    
    with content:
        with st.container(border=True):
            st.title("👨‍🍳 Login")
            st.write("Please log in to access your recipes.")
            
            # Makes it look like a real login form and save the username in session state for later use (not secure, just for demo)
            # also prefil the username field with the last entered username for better UX
            username = st.text_input("Username", value=st.session_state.get("username", ""))
            st.session_state.username = username
            st.text_input("Password", type="password")
            
            # only if the user has entered something in the username field, make the login button active and pressable
            if not username:
                if st.button("Log In", type="primary", width='stretch', disabled=True):
                    st.write("Please enter a username to log in.")
            else:
                if st.button("Log In", type="primary", width='stretch'):
                    st.session_state.authenticated = True
                    st.rerun()

def main():
    initialize_state()

    if not st.session_state.authenticated:
        login_screen()
        return

    # --- TOP TAB NAVIGATION ---
    # Only show the tabs if we are on the main pages (not deep in a recipe)
    # change background color of the following container
    with st.container(border=True):
        home_button, search_button, upload_button, goback_button, spacer, profile = st.columns([3, 3, 3, 1, 2, 3])
        
        with home_button:
            btn_type = "primary" if st.session_state.current_page == "Home" else "secondary"
            if st.button("Home", width='stretch', type=btn_type):
                if st.session_state.current_page != "Home":
                    switch_page("Home")

        with search_button:
            btn_type = "primary" if st.session_state.current_page == "Search" else "secondary"
            if st.button("Search", width='stretch', type=btn_type):
                if st.session_state.current_page != "Search":
                    switch_page("Search")

        with upload_button:
            btn_type = "primary" if st.session_state.current_page == "Upload" else "secondary"
            if st.button("Upload Ingredients", width='stretch', type=btn_type):
                if st.session_state.current_page != "Upload":
                    switch_page("Upload")

        with goback_button:
            if st.button("⬅️", width='stretch'):
                if st.session_state.page_history:
                    st.session_state.page_history.pop()  # Remove current page
                    if st.session_state.page_history:
                        last_page = st.session_state.page_history.pop()  # Get last page
                        switch_page(last_page)
                    else:
                        switch_page("Home")

        with profile:
            if st.button(f"👤 {st.session_state.username}", width='stretch'):
                #only show info for 5 seconds
                st.toast(f"Page does not yet exist.", icon="👤")


    # --- PAGE ROUTING ---
    if st.session_state.current_page == "Home":
        home.show()
    elif st.session_state.current_page == "Search":
        search.show()
    elif st.session_state.current_page == "Upload":
        upload.show()
    elif st.session_state.current_page == "Recipe Details":
        recipe_details.show()
    elif st.session_state.current_page == "Guide":
        guide.show()

if __name__ == "__main__":
    main()