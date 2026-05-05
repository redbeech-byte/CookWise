import streamlit as st

def switch_page(page_name, recipe_id=None, execute_func=None):
    """
    Update session state to switch the page.
    """
    # 1. Update recipe ID first if provided
    if recipe_id is not None:
        st.session_state.selected_recipe = recipe_id

    # 2. Update page history and current page
    if 'page_history' not in st.session_state:
        st.session_state.page_history = ["Home"]

    if not st.session_state.page_history or st.session_state.page_history[-1] != page_name:
        st.session_state.page_history.append(page_name)

    st.session_state.current_page = page_name

    # 3. Execute optional function LAST
    if execute_func:
        try:
            execute_func()
        except Exception as e:
            st.error(f"Error during page transition task: {e}")

    # Note: Streamlit handles the rerun automatically after this callback.
def go_back():
    if 'page_history' in st.session_state and st.session_state.page_history:
        # The last page in history is usually the CURRENT page
        st.session_state.page_history.pop()
        if st.session_state.page_history:
            last_page = st.session_state.page_history.pop()
            switch_page(last_page)
        else:
            switch_page("Home")
