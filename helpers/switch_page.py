import streamlit as st

def switch_page(page_name, recipe_id=None, execute_func=None):
    """
    Update session state to switch the page.
    """
    if execute_func:
        execute_func()
        
    if recipe_id is not None:
        st.session_state.selected_recipe = recipe_id

    if 'page_history' not in st.session_state:
        st.session_state.page_history = ["Home"]
    
    if not st.session_state.page_history or st.session_state.page_history[-1] != page_name:
        st.session_state.page_history.append(page_name)
        
    st.session_state.current_page = page_name
    
    # Force a rerun if we're not inside a callback to ensure immediate page switch
    # and cleanup of old elements.
    try:
        st.rerun()
    except Exception:
        # st.rerun() raises a specific exception to stop the script,
        # which is handled by Streamlit. If we're in a callback, this might fail or be a no-op.
        pass

def go_back():
    if 'page_history' in st.session_state and st.session_state.page_history:
        # The last page in history is usually the CURRENT page
        st.session_state.page_history.pop() 
        if st.session_state.page_history:
            last_page = st.session_state.page_history.pop()
            switch_page(last_page)
        else:
            switch_page("Home")
