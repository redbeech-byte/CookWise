import streamlit as st
import datetime
from helpers.supabase_client import get_profile, update_profile, get_saved_recipes, get_seen_recipes, get_cooked_recipes, remove_saved_recipe, update_password, delete_account, logout
from helpers.db import get_recipe_by_id
from helpers.switch_page import switch_page
from helpers.image_helper import display_recipe_image

# Available dietary restrictions / Preferences
RESTRICTIONS = ["Vegan", "Vegetarian", "Dairy-Free", "Gluten-Free", "Nut-Free", "Halal", "Kosher"]
PREFERENCES = ["Spicy", "Sweet", "Savory", "Umami", "Fast", "Slow", "Easy", "Hard"]

def show_title():
    return "My Profile & Library"
def show():

    
    profile = get_profile()
    if not profile:
        st.warning("Could not load your profile. Are you logged in?")
        return

    st.write(f"### Hello, {profile.get('username') or 'Chef'}! 🍳")
    
    tabs = st.tabs(["Personal Library", "Preferences", "Cooking History", "Recently Seen"])
    
    from helpers.nutrition_helper import get_recipe_nutrition

    with tabs[0]:
        st.subheader("Saved Recipes")
        saved = get_saved_recipes()
        if saved:
            cols_per_row = 3
            for i in range(0, len(saved), cols_per_row):
                cols = st.columns(cols_per_row)
                for j in range(cols_per_row):
                    if i + j < len(saved):
                        item = saved[i+j]
                        rid = item["recipe_id"]
                        r = get_recipe_by_id(rid)
                        if r:
                            with cols[j]:
                                with st.container(border=True):
                                    display_recipe_image(r.get('recipe_title', 'recipe'), key_suffix=f"save_{item['id']}")
                                    
                                    title = r.get("recipe_title", "Unknown Title")
                                    if len(title) > 50:
                                        title = title[:47] + "..."
                                        
                                    st.write(f"**{title}**")

                                    # Pre-load the nutrition data in the background
                                    get_recipe_nutrition(rid)

                                    st.write(f"🕒 Saved: {item['saved_at'][:10]}")
                                    
                                    st.write("")
                                    col_v, col_r = st.columns(2)
                                    with col_v:
                                        if st.button("👨‍🍳 View", key=f"view_save_{item['id']}", use_container_width=True):
                                            st.session_state.selected_recipe = rid
                                            switch_page("Recipe Details")
                                    with col_r:
                                        if st.button("❌ Remove", key=f"rm_save_{item['id']}", use_container_width=True):
                                            remove_saved_recipe(rid)
                                            st.rerun()
        else:
            st.info("You haven't saved any recipes yet.")
            
    with tabs[1]:
        st.subheader("Dietary Restrictions & Preferences")
        st.write("We use this to highlight recipes suited for you.")
        
        curr_rest = profile.get("dietary_restrictions") or []
        curr_pref = profile.get("cooking_preferences") or []
        
        st.write("#### Restrictions")
        selected_restrictions = []
        rest_cols = st.columns(4)
        for idx, rest in enumerate(RESTRICTIONS):
            with rest_cols[idx % 4]:
                is_toggled = st.toggle(rest, value=(rest in curr_rest))
                
                if rest == "Vegan" and is_toggled and "Vegan" not in curr_rest:
                    st.toast("We don't do that here...", icon="🥩")
                    logout()
                    st.session_state.authenticated = False
                    st.rerun()
                    
                if is_toggled:
                    selected_restrictions.append(rest)
                    
        st.write("#### Preferences")
        selected_preferences = []
        pref_cols = st.columns(4)
        for idx, pref in enumerate(PREFERENCES):
            with pref_cols[idx % 4]:
                if st.toggle(pref, value=(pref in curr_pref)):
                    selected_preferences.append(pref)
                    
        st.write("")
        if st.button("💾 Save Preferences", type="primary"):
            update_profile(selected_restrictions, selected_preferences)
            st.success("Preferences updated!")
            
        st.divider()
        st.subheader("Security & Account")
        
        col_sec1, col_sec2 = st.columns(2)
        with col_sec1:
            with st.container(border=True):
                st.write("**🔐 Change Password**")
                new_pw = st.text_input("New Password", type="password")
                conf_pw = st.text_input("Confirm Password", type="password")
                if st.button("Update Password"):
                    if new_pw and new_pw == conf_pw:
                        try:
                            update_password(new_pw)
                            st.success("Password updated successfully!")
                        except Exception as e:
                            st.error(f"Error: {e}")
                    else:
                        st.warning("Passwords must match and cannot be empty.")
                        
        with col_sec2:
            with st.container(border=True):
                st.write("**⚠️ Danger Zone**")
                st.write("Deleting your account is permanent. All saved recipes and cooking history will be lost.")
                confirm_del = st.checkbox("I understand the consequences, delete my account.")
                if st.button("❌ Delete Account", type="primary", disabled=not confirm_del):
                    try:
                        delete_account()
                        st.session_state.authenticated = False
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error deleting account: {str(e)}")
                
    with tabs[2]:
        st.subheader("Completed Recipes")
        cooked = get_cooked_recipes()
        if cooked:
            cols_per_row = 3
            for i in range(0, len(cooked), cols_per_row):
                cols = st.columns(cols_per_row)
                for j in range(cols_per_row):
                    if i + j < len(cooked):
                        item = cooked[i+j]
                        rid = item["recipe_id"]
                        r = get_recipe_by_id(rid)
                        if r:
                            with cols[j]:
                                with st.container(border=True):
                                    display_recipe_image(r.get('recipe_title', 'recipe'), key_suffix=f"cook_{item['id']}")
                                    
                                    title = r.get("recipe_title", "Unknown Title")
                                    if len(title) > 50:
                                        title = title[:47] + "..."
                                        
                                    st.write(f"**{title}**")

                                    # Pre-load the nutrition data in the background
                                    get_recipe_nutrition(rid)

                                    st.write(f"✅ Cooked: {item['cooked_at'][:10]}")
                                    
                                    st.write("")
                                    if st.button("👨‍🍳 View Recipe", key=f"view_cook_{item['id']}", use_container_width=True):
                                        st.session_state.selected_recipe = rid
                                        switch_page("Recipe Details")
        else:
            st.info("No recipes marked as cooked yet.")
            
    with tabs[3]:
        st.subheader("Recently Viewed")
        seen_list = get_seen_recipes()
        if seen_list:
            seen_ids = set()
            recent_items = []
            for item in seen_list:
                if item["recipe_id"] not in seen_ids:
                    seen_ids.add(item["recipe_id"])
                    recent_items.append(item)
                    
            cols_per_row = 3
            for i in range(0, len(recent_items), cols_per_row):
                cols = st.columns(cols_per_row)
                for j in range(cols_per_row):
                    if i + j < len(recent_items):
                        item = recent_items[i+j]
                        rid = item["recipe_id"]
                        r = get_recipe_by_id(rid)
                        if r:
                            with cols[j]:
                                with st.container(border=True):
                                    display_recipe_image(r.get('recipe_title', 'recipe'), key_suffix=f"seen_{item['id']}")
                                    
                                    title = r.get("recipe_title", "Unknown Title")
                                    if len(title) > 50:
                                        title = title[:47] + "..."
                                        
                                    st.write(f"**{title}**")

                                    # Pre-load the nutrition data in the background
                                    get_recipe_nutrition(rid)

                                    st.write(f"👀 Viewed: {item['seen_at'][:10]}")
                                    
                                    st.write("")
                                    if st.button("👨‍🍳 View Again", key=f"view_seen_{item['id']}", use_container_width=True):
                                        st.session_state.selected_recipe = rid
                                        switch_page("Recipe Details")
        else:
            st.write("No recently viewed recipes.")
            
