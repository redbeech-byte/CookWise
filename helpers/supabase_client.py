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
    return supabase.auth.sign_out()
    
def update_password(new_password):
    return supabase.auth.update_user({"password": new_password})

def delete_account():
    # Only Admin API can fully delete GoTrue auth users. For standard anon clients, we will delete their profile from public tables and sign them out.
    user = get_current_user()
    if user and hasattr(user, 'user') and user.user:
        user_id = user.user.id
        supabase.table("profiles").delete().eq("id", user_id).execute()
        return supabase.auth.sign_out()

# --- Database helpers ---

def get_profile():
    user = get_current_user()
    if not user or not user.user:
        return None
    res = supabase.table("user_profiles").select("*").eq("id", user.user.id).execute()
    return res.data[0] if res.data else None

def update_profile(dietary_restrictions, cooking_preferences):
    user = get_current_user()
    if user and user.user:
        supabase.table("user_profiles").update({
            "dietary_restrictions": dietary_restrictions,
            "cooking_preferences": cooking_preferences
        }).eq("id", user.user.id).execute()

def save_recipe(recipe_id):
    user = get_current_user()
    if user and user.user:
        try:
            supabase.table("saved_recipes").insert({
                "user_id": user.user.id,
                "recipe_id": recipe_id
            }).execute()
        except Exception:
            pass # Already saved

def remove_saved_recipe(recipe_id):
    user = get_current_user()
    if user and user.user:
        supabase.table("saved_recipes").delete().eq("user_id", user.user.id).eq("recipe_id", recipe_id).execute()

def mark_recipe_seen(recipe_id):
    user = get_current_user()
    if user and user.user:
        supabase.table("seen_recipes").insert({
            "user_id": user.user.id,
            "recipe_id": recipe_id
        }).execute()

def mark_recipe_cooked(recipe_id):
    user = get_current_user()
    if user and user.user:
        supabase.table("cooked_recipes").insert({
            "user_id": user.user.id,
            "recipe_id": recipe_id
        }).execute()

def get_saved_recipes():
    user = get_current_user()
    if user and user.user:
        res = supabase.table("saved_recipes").select("*").eq("user_id", user.user.id).order("saved_at", desc=True).execute()
        return res.data
    return []

def get_seen_recipes():
    user = get_current_user()
    if user and user.user:
        res = supabase.table("seen_recipes").select("*").eq("user_id", user.user.id).order("seen_at", desc=True).limit(50).execute()
        return res.data
    return []

def get_cooked_recipes():
    user = get_current_user()
    if user and user.user:
        res = supabase.table("cooked_recipes").select("*").eq("user_id", user.user.id).order("cooked_at", desc=True).execute()
        return res.data
    return []
