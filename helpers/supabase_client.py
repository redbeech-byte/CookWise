import streamlit as st
from supabase import create_client, Client

@st.cache_resource
def init_supabase() -> Client:
    url: str = st.secrets["SUPABASE_URL"]
    key: str = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase: Client = init_supabase()

def get_current_user():
    return supabase.auth.get_user()

def login(email, password):
    return supabase.auth.sign_in_with_password({"email": email, "password": password})

def signup(email, password, username):
    # Pass username in user metadata
    return supabase.auth.sign_up({
        "email": email, 
        "password": password, 
        "options": {
            "data": {"username": username}
        }
    })

def logout():
    # clear session state and cache related to user
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.cache_data.clear()
    
    return supabase.auth.sign_out()
    
def update_password(new_password):
    return supabase.auth.update_user({"password": new_password})

def delete_account():
    user = get_current_user()
    if user and getattr(user, 'user', None):
        user_id = user.user.id
        # Delete profile data
        supabase.table("user_profiles").delete().eq("id", user_id).execute()
        # Sign out (Account deletion itself usually requires admin API or re-auth)
        return logout()

# --- Database helpers ---

def get_profile():
    user = get_current_user()
    if not user or not getattr(user, 'user', None):
        return None
        
    user_id = user.user.id
    res = supabase.table("user_profiles").select("*").eq("id", user_id).execute()
    
    if not res.data:
        # SELF-HEALING: Profile missing but user exists in Auth. Create it now.
        username = user.user.user_metadata.get("username", "Chef")
        try:
            supabase.table("user_profiles").insert({
                "id": user_id,
                "username": username
            }).execute()
            # Retry fetch
            res = supabase.table("user_profiles").select("*").eq("id", user_id).execute()
        except Exception as e:
            st.error(f"Failed to create missing profile: {e}")
            return None
            
    return res.data[0] if res.data else None

def update_profile(dietary_restrictions, cooking_preferences):
    user = get_current_user()
    if user and getattr(user, 'user', None):
        supabase.table("user_profiles").update({
            "dietary_restrictions": dietary_restrictions,
            "cooking_preferences": cooking_preferences
        }).eq("id", user.user.id).execute()

def save_recipe(recipe_id):
    user = get_current_user()
    if user and getattr(user, 'user', None):
        try:
            supabase.table("saved_recipes").insert({
                "user_id": user.user.id,
                "recipe_id": recipe_id
            }).execute()
            get_saved_recipes.clear()
        except Exception:
            pass 

def remove_saved_recipe(recipe_id):
    user = get_current_user()
    if user and getattr(user, 'user', None):
        supabase.table("saved_recipes").delete().eq("user_id", user.user.id).eq("recipe_id", recipe_id).execute()
        get_saved_recipes.clear()

def mark_recipe_seen(recipe_id):
    user = get_current_user()
    if user and getattr(user, 'user', None):
        supabase.table("seen_recipes").insert({
            "user_id": user.user.id,
            "recipe_id": recipe_id
        }).execute()
        get_seen_recipes.clear()

def mark_recipe_cooked(recipe_id):
    user = get_current_user()
    if user and getattr(user, 'user', None):
        supabase.table("cooked_recipes").insert({
            "user_id": user.user.id,
            "recipe_id": recipe_id
        }).execute()
        get_cooked_recipes.clear()

@st.cache_data(ttl=60)
def get_saved_recipes():
    user = get_current_user()
    if user and getattr(user, 'user', None):
        res = supabase.table("saved_recipes").select("*").eq("user_id", user.user.id).order("saved_at", desc=True).execute()
        return res.data
    return []

@st.cache_data(ttl=60)
def get_seen_recipes():
    user = get_current_user()
    if user and getattr(user, 'user', None):
        res = supabase.table("seen_recipes").select("*").eq("user_id", user.user.id).order("seen_at", desc=True).limit(50).execute()
        return res.data
    return []

@st.cache_data(ttl=60)
def get_cooked_recipes():
    user = get_current_user()
    if user and getattr(user, 'user', None):
        res = supabase.table("cooked_recipes").select("*").eq("user_id", user.user.id).order("cooked_at", desc=True).execute()
        return res.data
    return []
