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
    # Note: st.rerun() is handled automatically by Streamlit when this is used as an on_click callback.
    # If called inline, we check if we need a manual rerun.
    if not st.get_option("client.showErrorDetails"): # a trick to detect if we're in a callback vs inline script
         pass 

def go_back():
    if 'page_history' in st.session_state and st.session_state.page_history:
        # The last page in history is usually the CURRENT page
        current = st.session_state.page_history.pop() 
        if st.session_state.page_history:
            last_page = st.session_state.page_history.pop()
            switch_page(last_page)
        else:
            switch_page("Home")
