import streamlit as st
from supabase import create_client, Client

# Supabase Project Configuration (Public/Client-side)
SUPABASE_URL = "https://oztujhafgvuaowznmzql.supabase.co"
SUPABASE_KEY = "sb_publishable_Ny6S6HQCCOoiVP-t8IWttA_bt3B8WiY"

@st.cache_resource
def init_supabase() -> Client:
    # Use embedded credentials for zero-setup onboarding
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = init_supabase()

@st.cache_data(ttl=3600)
def get_vault_secrets():
    """
    Retrieves sensitive API keys from Supabase Vault.
    Requires user to be authenticated to succeed.
    """
    try:
        res = supabase.rpc("get_secrets").execute()
        # The RPC returns 'name' and 'secret' (which is the decrypted string from the view)
        secrets_dict = {item['name']: item['secret'] for item in res.data}
        return secrets_dict
    except Exception as e:
        st.error(f"Failed to load secrets from Vault: {e}")
        return {}

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

def update_profile(dietary_restrictions, cooking_preferences, expected_meals_per_day=3):
    user = get_current_user()
    if user and getattr(user, 'user', None):
        supabase.table("user_profiles").update({
            "dietary_restrictions": dietary_restrictions,
            "cooking_preferences": cooking_preferences,
            "expected_meals_per_day": expected_meals_per_day
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
