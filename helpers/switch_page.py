import streamlit as st

# The helper function for navigating through the app's pages.
def switch_page(page_name, recipe_id=None, execute_func=None):
    """
    Updating session state so the app switches to another page.
    """
    # Saving the selected recipe first when a page transition depends on it.
    # This lets pages like Recipe Details open with the correct recipe context.
    if recipe_id is not None:
        st.session_state.selected_recipe = recipe_id

    # Initializing page history if it does not exist yet.
    # The app uses this history for the custom back-button behavior.
    if 'page_history' not in st.session_state:
        st.session_state.page_history = ["Home"]

    # Appending the new page only if it is not already the latest entry.
    # This avoids stacking duplicate history entries during repeated reruns.
    if not st.session_state.page_history or st.session_state.page_history[-1] != page_name:
        st.session_state.page_history.append(page_name)

    # Updating the current page so main_app.py knows which view to render next.
    st.session_state.current_page = page_name

    # Running an optional extra task after the page state has been updated.
    # This is useful for transitions that need side effects beyond navigation.
    if execute_func:
        try:
            execute_func()
        except Exception as e:
            # Showing a readable error instead of breaking the whole page switch.
            st.error(f"Error during page transition task: {e}")

    # Letting Streamlit handle the rerun automatically after the callback finishes.


def go_back():
    # Moving backward through the custom page history stored in session state.
    if 'page_history' in st.session_state and st.session_state.page_history:
        # Removing the latest entry first because it is usually the current page.
        st.session_state.page_history.pop()

        if st.session_state.page_history:
            # Pulling the previous page from history and switching back to it.
            # `switch_page()` may add that page again, which is acceptable here
            # because we are restoring it as the new current page.
            last_page = st.session_state.page_history.pop()
            switch_page(last_page)
        else:
            # Falling back to Home if there is no earlier page left in history.
            switch_page("Home")
