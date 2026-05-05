import streamlit as st
import datetime
from helpers.supabase_client import get_profile, update_profile, get_saved_recipes, get_seen_recipes, get_cooked_recipes, remove_saved_recipe, update_password, delete_account, logout
from helpers.db import get_recipe_by_id, deduplicate_recipes
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
    
    tabs = st.tabs(["Personal Library", "Preferences", "Cooking History", "Security"])
    
    with tabs[0]:
        st.subheader("Saved Recipes")
        saved_raw = get_saved_recipes()
        saved_hydrated = []
        for item in saved_raw:
            r = get_recipe_by_id(item["recipe_id"])
            if r:
                r_copy = r.copy()
                r_copy['_saved_at'] = item['saved_at']
                r_copy['_item_id'] = item['id']
                saved_hydrated.append(r_copy)
        
        saved = deduplicate_recipes(saved_hydrated)
        
        if saved:
            cols_per_row = 3
            for i in range(0, len(saved), cols_per_row):
                cols = st.columns(cols_per_row)
                for j in range(cols_per_row):
                    if i + j < len(saved):
                        r = saved[i+j]
                        rid = r["recipe_id"]
                        with cols[j]:
                            with st.container(border=True):
                                display_recipe_image(r.get('recipe_title', 'recipe'), key_suffix=f"save_{r['_item_id']}")
                                title = r.get("recipe_title", "Unknown Title")
                                if len(title) > 50:
                                    title = title[:47] + "..."
                                st.write(f"**{title}**")
                                st.write(f"🕒 Saved: {r['_saved_at'][:10]}")
                                st.write("")
                                col_v, col_r = st.columns(2)
                                with col_v:
                                    st.button(
                                        "👨‍🍳 View", 
                                        key=f"view_save_{r['_item_id']}", 
                                        use_container_width=True,
                                        on_click=switch_page,
                                        args=("Recipe Details", rid)
                                    )
                                with col_r:
                                    st.button(
                                        "❌ Remove", 
                                        key=f"rm_save_{r['_item_id']}", 
                                        use_container_width=True,
                                        on_click=remove_saved_recipe,
                                        args=(rid,)
                                    )
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
                is_toggled = st.toggle(rest, value=(rest in curr_rest), key=f"rest_{rest}")
                if is_toggled:
                    selected_restrictions.append(rest)
                    
        st.write("#### Preferences")
        selected_preferences = []
        pref_cols = st.columns(4)
        for idx, pref in enumerate(PREFERENCES):
            with pref_cols[idx % 4]:
                if st.toggle(pref, value=(pref in curr_pref), key=f"pref_{pref}"):
                    selected_preferences.append(pref)
                    
        st.write("")
        def save_prefs():
            update_profile(selected_restrictions, selected_preferences)
            st.toast("Preferences updated!")
            
        st.button("💾 Save Preferences", type="primary", on_click=save_prefs)
                
    with tabs[2]:
        st.subheader("Completed Recipes")
        cooked_raw = get_cooked_recipes()
        cooked_hydrated = []
        for item in cooked_raw:
            r = get_recipe_by_id(item["recipe_id"])
            if r:
                r_copy = r.copy()
                r_copy['_cooked_at'] = item['cooked_at']
                r_copy['_item_id'] = item['id']
                cooked_hydrated.append(r_copy)
        
        cooked = deduplicate_recipes(cooked_hydrated)
        
        if cooked:
            cols_per_row = 3
            for i in range(0, len(cooked), cols_per_row):
                cols = st.columns(cols_per_row)
                for j in range(cols_per_row):
                    if i + j < len(cooked):
                        r = cooked[i+j]
                        rid = r["recipe_id"]
                        with cols[j]:
                            with st.container(border=True):
                                display_recipe_image(r.get('recipe_title', 'recipe'), key_suffix=f"cook_{r['_item_id']}")
                                title = r.get("recipe_title", "Unknown Title")
                                if len(title) > 50:
                                    title = title[:47] + "..."
                                st.write(f"**{title}**")
                                st.write(f"✅ Cooked: {r['_cooked_at'][:10]}")
                                st.write("")
                                st.button(
                                    "👨‍🍳 View Recipe", 
                                    key=f"view_cook_{r['_item_id']}", 
                                    use_container_width=True,
                                    on_click=switch_page,
                                    args=("Recipe Details", rid)
                                )
        else:
            st.info("No recipes marked as cooked yet.")
            
    with tabs[3]:
        st.subheader("Security & Account")
        col_sec1, col_sec2 = st.columns(2)
        with col_sec1:
            with st.container(border=True):
                st.write("**🔐 Change Password**")
                new_pw = st.text_input("New Password", type="password")
                conf_pw = st.text_input("Confirm Password", type="password")
                
                def do_update_pw():
                    if new_pw and new_pw == conf_pw:
                        try:
                            update_password(new_pw)
                            st.toast("Password updated successfully!", icon="✅")
                        except Exception as e:
                            st.error(f"Error: {e}")
                    else:
                        st.warning("Passwords must match and cannot be empty.")
                
                st.button("Update Password", on_click=do_update_pw)
                        
        with col_sec2:
            with st.container(border=True):
                st.write("**⚠️ Danger Zone**")
                st.write("Deleting your account is permanent.")
                confirm_del = st.checkbox("I understand the consequences, delete my account.")
                
                def do_delete():
                    try:
                        delete_account()
                    except Exception as e:
                        st.error(f"Error deleting account: {str(e)}")

                st.button("❌ Delete Account", type="primary", disabled=not confirm_del, on_click=do_delete)
