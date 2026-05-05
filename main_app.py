import streamlit as st
import time
import os
from helpers.switch_page import switch_page, go_back
from helpers.supabase_client import login, signup, logout, get_current_user

# Global app config
st.set_page_config(page_title="CookWise", layout="wide")

# Robust absolute path for the logo to fix friend's macOS issue
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
logo_path = os.path.join(CURRENT_DIR, "pictures", "logoName.svg")

if os.path.exists(logo_path):
    st.logo(logo_path, size="large")

PAGE_TITLES = {
    "Home": lambda: "Home",
    "Search": lambda: "Search Recipes",
    "Scan": lambda: "FridgeScan",
    "Recipe Details": lambda: "Recipe Details",
    "Profile": lambda: "Profile",
    "Guide": lambda: "Cooking Guide"
}

def initialize_state():
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "Home"
    if 'selected_recipe' not in st.session_state:
        st.session_state.selected_recipe = None
    if 'page_history' not in st.session_state:
        st.session_state.page_history = ["Home"]
    
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
                    new_password = st.text_input("Password", type="password", help="Minimum 6 characters")
                    submitted_signup = st.form_submit_button("Sign Up", type="primary", use_container_width=True)
                    if submitted_signup:
                        if len(new_password) < 6:
                            st.error("Password must be at least 6 characters long.")
                        elif not new_username:
                            st.error("Please enter a username.")
                        else:
                            try:
                                res = signup(new_email, new_password, new_username)
                                if res and res.user:
                                    st.success("Signup successful! Log in to get started.")
                                    st.info("Note: If you didn't see a success message before but it says user exists, try logging in.")
                            except Exception as e:
                                err_str = str(e).lower()
                                if "already registered" in err_str or "already exists" in err_str:
                                    st.warning("This email is already registered. Try logging in or resetting your password.")
                                else:
                                    st.error(f"Signup failed: {e}")

def main():
    initialize_state()

    if not st.session_state.get('authenticated'):
        auth_screen()
        return

    # --- TOP TAB NAVIGATION ---
    _, home_button, search_button, scan_button, profile_btn, logout_btn, goback_button = st.columns([5, 2, 2, 2, 2, 1, 1], vertical_alignment="bottom")

    with home_button:
        btn_type = "primary" if st.session_state.current_page == "Home" else "secondary"
        st.button("Home", width='stretch', type=btn_type, on_click=switch_page, args=("Home",), key="nav_home")

    with search_button:
        btn_type = "primary" if st.session_state.current_page == "Search" else "secondary"
        st.button("Search", width='stretch', type=btn_type, on_click=switch_page, args=("Search",), key="nav_search")

    with scan_button:
        btn_type = "primary" if st.session_state.current_page == "Scan" else "secondary"
        st.button("FridgeScan", width='stretch', type=btn_type, on_click=switch_page, args=("Scan",), key="nav_scan")

    with goback_button:
        st.button("⬅️", width='stretch', help="Go Back", on_click=go_back, key="nav_back")

    with profile_btn:
        btn_type = "primary" if st.session_state.current_page == "Profile" else "secondary"
        st.button(f"👤 Profile", width='stretch', type=btn_type, on_click=switch_page, args=("Profile",), key="nav_profile")

    with logout_btn:
        def do_logout():
            logout()
        st.button("🚪", width='stretch', type="secondary", help="Logout", on_click=do_logout, key="nav_logout")

    st.divider()

    # --- PAGE CONTENT (double-buffered) ---
    # Two st.empty() slots at distinct script positions. We alternate which
    # one renders the active page on every navigation. The old page is still
    # in (say) slot_a while the new page paints into slot_b — physically
    # different positions in the element tree, so Streamlit's diff cannot
    # match dissimilar layouts and reparent leftover children. After painting
    # the active slot, we explicitly empty the inactive one so the previous
    # render is fully evicted from the DOM.
    slot_a = st.empty()
    slot_b = st.empty()

    curr = st.session_state.current_page
    if st.session_state.get('_last_rendered_page') != curr:
        # Flip the active slot on every page change
        st.session_state._active_slot = 1 - st.session_state.get('_active_slot', 0)
        st.session_state._last_rendered_page = curr

    active_idx = st.session_state.get('_active_slot', 0)
    active_slot = slot_a if active_idx == 0 else slot_b
    inactive_slot = slot_b if active_idx == 0 else slot_a

    inactive_slot.empty()

    with active_slot.container():
        title_text = PAGE_TITLES.get(curr, lambda: curr)()
        st.title(title_text)

        if curr == "Home":
            from views import home
            home.show()
        elif curr == "Search":
            from views import search
            search.show()
        elif curr == "Scan":
            from views import scan
            scan.show()
        elif curr == "Recipe Details":
            from views import recipe_details
            recipe_details.show()
        elif curr == "Profile":
            from views import profile
            profile.show()
        elif curr == "Guide":
            from views import guide
            guide.show()

if __name__ == "__main__":
    main()
