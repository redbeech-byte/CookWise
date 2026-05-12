import streamlit as st
import time
import os
from helpers.switch_page import switch_page, go_back
# Importing from the supabase helper creates a client that is cached.
from helpers.supabase_client import login, signup, logout, get_current_user 

# Configuring the global Streamlit app window.
st.set_page_config(page_title="CookWise", layout="wide")

# Building a project-relative path to the logo.
# This avoids hard-coded personal paths that would break on other machines.
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
logo_path = os.path.join(CURRENT_DIR, "pictures", "logoName.svg")

# Starting the app with the CookWise logo in the shared top UI area.
st.logo(logo_path, size="large")

# Mapping internal page names to the titles shown in the UI.
# Keeping titles in one place makes them easier to maintain consistently.
# And the title can be displayed outside the page modules, which looks better in the top tab navigation.
PAGE_TITLES = {
    "Home": lambda: "Home",
    "Search": lambda: "Search Recipes",
    "Scan": lambda: "FridgeScan",
    "Recipe Details": lambda: "Recipe Details",
    "Profile": lambda: "Profile",
    "Guide": lambda: "Cooking Guide"
}


def initialize_state():
    # Storing the current page in session state.
    # Without session state, Streamlit reruns would forget navigation state.
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "Home"

    # Storing the currently selected recipe.
    # This is needed by pages like Recipe Details and Guide.
    if 'selected_recipe' not in st.session_state:
        st.session_state.selected_recipe = None

    # Storing simple page history for the custom back button.
    if 'page_history' not in st.session_state:
        st.session_state.page_history = ["Home"]
    
    # Checking authentication only once when the session starts.
    # This avoids repeated remote auth checks during normal reruns.
    if 'authenticated' not in st.session_state:
        try:
            user = get_current_user()

            # Saving the logged-in user state if Supabase returns a valid session.
            if user and hasattr(user, 'user') and user.user:
                st.session_state.authenticated = True
                st.session_state.user_id = user.user.id
                st.session_state.username = user.user.user_metadata.get('username', 'Chef')
            else:
                st.session_state.authenticated = False
        except Exception:
            # Falling back safely to the logged-out state if the auth check fails.
            st.session_state.authenticated = False


def auth_screen():
    # Creating 3 columns so the auth box appears centered on the screen.
    spacer_left, content, spacer_right = st.columns([1, 2, 1])
    with content:
        # Wrapping the login/signup UI in a bordered container for structure.
        with st.container(border=True):
            st.title("👨‍🍳 Login / Signup")
            st.write("Please log in or sign up to access your recipes.")
            
            # Splitting authentication into separate login and signup tabs.
            tab1, tab2 = st.tabs(["Login", "Sign Up"])
            with tab1:
                # Grouping login inputs inside a form so the logic only runs
                # when the user actively submits the form.
                with st.form("login_form"):
                    email = st.text_input("Email")
                    password = st.text_input("Password", type="password")
                    submitted = st.form_submit_button("Log In", type="primary", use_container_width=True)
                    if submitted:
                        try:
                            # Sending the entered credentials to the secure Supabase login helper.
                            res = login(email, password)

                            # Saving the returned user session if login succeeds.
                            if res and res.user:
                                st.session_state.authenticated = True
                                st.session_state.user_id = res.user.id
                                st.session_state.username = res.user.user_metadata.get('username', 'Chef')

                                # Triggering a rerun so the main app UI appears immediately.
                                st.rerun()
                        except Exception as e:
                            # Showing a readable error instead of crashing the app.
                            st.error(f"Login failed: {e}")
            with tab2:
                with st.form("signup_form"):
                    new_email = st.text_input("Email")
                    new_username = st.text_input("Username")
                    new_password = st.text_input("Password", type="password", help="Minimum 6 characters")
                    submitted_signup = st.form_submit_button("Sign Up", type="primary", use_container_width=True)
                    if submitted_signup:
                        # Validating basic signup input before sending it remotely.
                        if len(new_password) < 6:
                            st.error("Password must be at least 6 characters long.")
                        elif not new_username:
                            st.error("Please enter a username.")
                        else:
                            try:
                                # The signup helper creates a new user in Supabase Auth.
                                res = signup(new_email, new_password, new_username) 
                                if res and res.user:
                                    st.success("Signup successful! Log in to get started.")
                                    st.info("Note: If you didn't see a success message before but it says user exists, try logging in.")
                            except Exception as e:
                                err_str = str(e).lower()

                                # Interpreting common signup errors more helpfully for the user.
                                if "already registered" in err_str or "already exists" in err_str:
                                    st.warning("This email is already registered. Try logging in or resetting your password.")
                                else:
                                    st.error(f"Signup failed: {e}")


def main():
    # Preparing session state before rendering any UI including auth check
    initialize_state()

    # Showing only the auth screen when the user is not logged in.
    # Returning here prevents the rest of the app from rendering.
    if not st.session_state.get('authenticated'):
        auth_screen()
        return

    # Reading the currently active page from session state.
    curr = st.session_state.current_page

    # Looking up the visible title for the current page.
    # Falling back to the raw page name if it is missing from PAGE_TITLES.
    title_text = PAGE_TITLES.get(curr, lambda: curr)()

    # --- TOP TAB NAVIGATION (with inline page title) ---
    # Creating one row with a title area and navigation buttons.
    title_col, home_button, search_button, scan_button, profile_btn, logout_btn, goback_button = st.columns([5, 2, 2, 2, 2, 1, 1], vertical_alignment="bottom")

    with title_col:
        st.title(title_text)

    with home_button:
        # Highlighting the active page button using the "primary" style.
        # Creating the actual button, making sure loading the page is triggered by click and creating a key for Streamlit identification. 
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
        # Wrapping logout in a small helper function so `on_click` receives
        # the function itself instead of executing logout immediately.
        def do_logout():
            logout() # Calling the secure Supabase logout helper to clear the session server-side and clear streamlit cache and session state locally.
        st.button("🚪", width='stretch', type="secondary", help="Logout", on_click=do_logout, key="nav_logout")

    # Visually separating the top navigation from the page content below.
    st.divider()

    # --- PAGE CONTENT (double-buffered) ---
    # Creating placeholder slots to avoid residual UI elements from previous pages when switching pages with different layouts.
    slot_a = st.empty()
    slot_b = st.empty()

    if st.session_state.get('_last_rendered_page') != curr:
        # Alternation between slot_a and slot_b when loading new pages.
        st.session_state._active_slot = 1 - st.session_state.get('_active_slot', 0)
        st.session_state._last_rendered_page = curr

    active_idx = st.session_state.get('_active_slot', 0)
    active_slot = slot_a if active_idx == 0 else slot_b
    inactive_slot = slot_b if active_idx == 0 else slot_a

    # Clearing the inactive slot so old page content is removed explicitly.
    inactive_slot.empty()

    # Rendering the current page inside the active slot. Router logic
    with active_slot.container():
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


# Running main() only when this file is executed directly.
# Importing this file elsewhere will not trigger the app automatically.
if __name__ == "__main__":
    main()
