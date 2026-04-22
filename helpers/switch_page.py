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
    # Note: st.rerun() is a no-op inside on_click callbacks because Streamlit naturally reruns 
    # the script after a callback. If switch_page is used inline (if st.button(): switch_page()), 
    # you MUST call st.rerun() manually after switch_page(), OR convert it to an on_click callback.

def go_back():
    if 'page_history' in st.session_state and st.session_state.page_history:
        st.session_state.page_history.pop()  # Remove current page
        if st.session_state.page_history:
            last_page = st.session_state.page_history.pop()  # Get last page
            switch_page(last_page)
        else:
            switch_page("Home")
