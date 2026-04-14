import streamlit as st

if "page_history" not in st.session_state:
    st.session_state.page_history = []

def switch_page(page_name):
    # Only append if not already on this page
    if not st.session_state.page_history or st.session_state.page_history[-1] != page_name:
        st.session_state.page_history.append(page_name)
        
    st.session_state.current_page = page_name
    st.rerun()
