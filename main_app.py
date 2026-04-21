
from views import guide, home, recipe_details, search, profile, scan
from helpers.switch_page import switch_page
from helpers.supabase_client import login, signup, logout, get_current_user
import time
import streamlit as st

st.set_page_config(page_title="CookWise", layout="wide")
st.logo("/Users/geromeracordon/Dokumente/CS/project/github/CookWise/pictures/logoName.svg", size="large")


PAGE_TITLES = {
    "Home": home.show_title,
    "Search": search.show_title,
    "Scan": scan.show_title,
    "Recipe Details": recipe_details.show_title,
    "Profile": profile.show_title,
    "Guide": guide.show_title
}


def initialize_state():
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "Home"
    if 'selected_recipe' not in st.session_state:
        st.session_state.selected_recipe = None
    if 'page_history' not in st.session_state:
        st.session_state.page_history = ["Home"]
    
    # Check supabase session ONLY if we haven't initialized it yet
    if 'authenticated' not in st.session_state:
        try:
            user = get_current_user()
            if user and hasattr(user, 'user') and user.user:
                st.session_state.authenticated = True
                st.session_state.user_id = user.user.id
                st.session_state.username = user.user.user_metadata.get('username', 'Chef')
            else:
                st.session_state.authenticated = False
        except Exception:
            st.session_state.authenticated = False

def auth_screen():
    # Squeezes the login box into the middle of the screen
    spacer_left, content, spacer_right = st.columns([1, 2, 1])
    
    with content:
        with st.container(border=True):
            st.title("👨‍🍳 Login / Signup")
            st.write("Please log in or sign up to access your recipes.")
            
            tab1, tab2 = st.tabs(["Login", "Sign Up"])
            
            with tab1:
                with st.form("login_form"):
                    email = st.text_input("Email")
                    password = st.text_input("Password", type="password")
                    submitted = st.form_submit_button("Log In", type="primary", use_container_width=True)
                    if submitted:
                        try:
                            res = login(email, password)
                            if res and res.user:
                                st.session_state.authenticated = True
                                st.session_state.user_id = res.user.id
                                st.session_state.username = res.user.user_metadata.get('username', 'Chef')
                                st.rerun()
                        except Exception as e:
                            st.error(f"Login failed: {e}")
                            
            with tab2:
                with st.form("signup_form"):
                    new_email = st.text_input("Email")
                    new_username = st.text_input("Username")
                    new_password = st.text_input("Password", type="password")
                    submitted_signup = st.form_submit_button("Sign Up", type="primary", use_container_width=True)
                    if submitted_signup:
                        try:
                            res = signup(new_email, new_password, new_username)
                            if res and res.user:
                                st.success("Signup successful! Please confirm your email or log in if auto-confirmed.")
                        except Exception as e:
                            st.error(f"Signup failed: {e}")

def main():
    initialize_state()

    if not st.session_state.authenticated:
        auth_screen()
        return




    # --- TOP TAB NAVIGATION ---
    # Only show the tabs if we are on the main pages (not deep in a recipe)
    # change background color of the following container
    with st.container(border=False):
        page_title,home_button, search_button, scan_button, profile_btn, logout_btn, goback_button = st.columns([5, 2, 2, 2, 2, 1, 1], vertical_alignment="bottom")
        
        with page_title:
            #show the title of the page that will be displayed below the navigation bar
            st.title(PAGE_TITLES.get(st.session_state.current_page, lambda: st.session_state.current_page)())
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

        with scan_button:
            btn_type = "primary" if st.session_state.current_page == "Scan" else "secondary"
            if st.button("FridgeScan", width='stretch', type=btn_type):
                if st.session_state.current_page != "Scan":
                    switch_page("Scan")

        with goback_button:
            if st.button("⬅️", width='stretch', help="Go Back"):
                if st.session_state.page_history:
                    st.session_state.page_history.pop()  # Remove current page
                    if st.session_state.page_history:
                        last_page = st.session_state.page_history.pop()  # Get last page
                        switch_page(last_page)
                    else:
                        switch_page("Home")

        with profile_btn:
            btn_type = "primary" if st.session_state.current_page == "Profile" else "secondary"
            if st.button(f"👤 Profile", width='stretch', type=btn_type):
                if st.session_state.current_page != "Profile":
                    switch_page("Profile")

        with logout_btn:
            if st.button("🚪", width='stretch', type="secondary", help="Logout"):
                logout()
                st.session_state.authenticated = False
                st.rerun()

    st.divider()  # Add a divider below the navigation bar

    # --- PAGE ROUTING ---
    if st.session_state.current_page == "Home":
        home.show()
    elif st.session_state.current_page == "Search":
        search.show()
    elif st.session_state.current_page == "Scan":
        scan.show()
    elif st.session_state.current_page == "Recipe Details":
        recipe_details.show()
    elif st.session_state.current_page == "Profile":
        profile.show()
    elif st.session_state.current_page == "Guide":
        guide.show()

if __name__ == "__main__":
    main()