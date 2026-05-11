import streamlit as st
from supabase import create_client, Client

# Supabase Project Configuration (Public/Client-side)
# These values connect the Streamlit app to the shared CookWise Supabase project.
# The key is publishable, so it is meant for client-side access and still depends
# on Supabase row-level security policies for protecting user data.
SUPABASE_URL = "https://oztujhafgvuaowznmzql.supabase.co"
SUPABASE_KEY = "sb_publishable_Ny6S6HQCCOoiVP-t8IWttA_bt3B8WiY"


@st.cache_resource
def init_supabase() -> Client:
    """
    Create the Supabase client once and reuse it across the Streamlit app.

    Streamlit reruns the script often, so caching the client avoids rebuilding
    the connection object every time the UI updates.
    """
    # Use embedded credentials for zero-setup onboarding.
    # This lets the app start without requiring each user to configure secrets locally.
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# Shared Supabase client used by the authentication and database helper functions below.
# Keeping one shared client also makes the rest of the file easier to read.
supabase: Client = init_supabase()


@st.cache_data(ttl=3600)
def get_vault_secrets():
    """
    Retrieves sensitive API keys from Supabase Vault.
    Requires user to be authenticated to succeed.

    The app uses this for secrets that should not be hardcoded directly in the
    Python files, such as external API keys used by helper modules.
    """
    try:
        # Calls the database function that exposes the secrets available to this user/session.
        res = supabase.rpc("get_secrets").execute()
        # The RPC returns rows with 'name' and 'secret'. Turning them into a dictionary
        # makes later lookups simpler, for example secrets["GEMINI_API_KEY"].
        secrets_dict = {item['name']: item['secret'] for item in res.data}
        return secrets_dict
    except Exception as e:
        # If Vault access fails, show the error in the app and return an empty dictionary
        # so callers can decide whether to fall back to local Streamlit secrets.
        st.error(f"Failed to load secrets from Vault: {e}")
        return {}


def get_current_user():
    """Return the currently authenticated Supabase user, if one exists."""
    # Supabase stores the auth result under a nested `.user` object, which is why
    # the other helpers check for both the response and the actual user inside it.
    return supabase.auth.get_user()


def login(email, password):
    """Sign in an existing user with email and password."""
    # Supabase handles the session creation and stores the login state for later requests.
    return supabase.auth.sign_in_with_password({"email": email, "password": password})


def signup(email, password, username):
    """Create a new user account and store the username as metadata."""
    # Pass username in user metadata so it is available immediately after signup,
    # before or while the profile row is created in the database.
    return supabase.auth.sign_up({
        "email": email,
        "password": password,
        "options": {
            "data": {"username": username}
        }
    })


def logout():
    """Clear local Streamlit state and sign the user out of Supabase."""
    # Clear all Streamlit session values so the next user does not see old UI state.
    for key in list(st.session_state.keys()):
        del st.session_state[key]

    # Cached database results may contain user-specific data, so they are cleared on logout.
    st.cache_data.clear()

    return supabase.auth.sign_out()


def update_password(new_password):
    """Update the logged-in user's password in Supabase Auth."""
    # This only works for an authenticated user session.
    return supabase.auth.update_user({"password": new_password})


def delete_account():
    """Remove the user's profile data and sign them out locally."""
    user = get_current_user()
    if user and getattr(user, 'user', None):
        user_id = user.user.id
        # Delete the app-specific profile row connected to this authenticated user.
        supabase.table("user_profiles").delete().eq("id", user_id).execute()
        # Sign out afterward. Full Supabase Auth account deletion usually requires
        # admin API access or re-authentication, so this handles the app-level cleanup.
        return logout()


# --- Database helpers ---

def get_profile():
    """Fetch the current user's profile, creating it if it is missing."""
    user = get_current_user()
    if not user or not getattr(user, 'user', None):
        return None

    user_id = user.user.id
    # Each profile row uses the Supabase Auth user id as its primary identifier.
    res = supabase.table("user_profiles").select("*").eq("id", user_id).execute()

    if not res.data:
        # SELF-HEALING: Profile missing but user exists in Auth. Create it now.
        # This helps avoid broken states after signup or if profile creation failed earlier.
        username = user.user.user_metadata.get("username", "Chef")
        try:
            supabase.table("user_profiles").insert({
                "id": user_id,
                "username": username
            }).execute()
            # Retry fetch now that the missing profile has been created.
            res = supabase.table("user_profiles").select("*").eq("id", user_id).execute()
        except Exception as e:
            # If profile recovery fails, return None so the calling page can handle it safely.
            st.error(f"Failed to create missing profile: {e}")
            return None
            
    # There should only be one profile per user id, so return the first matching row.
    return res.data[0] if res.data else None


def update_profile(dietary_restrictions, cooking_preferences, expected_meals_per_day=3):
    """Save the user's food preferences and expected daily meal count."""
    user = get_current_user()
    if user and getattr(user, 'user', None):
        # Store the settings that personalize recipe recommendations and nutrition views.
        supabase.table("user_profiles").update({
            "dietary_restrictions": dietary_restrictions,
            "cooking_preferences": cooking_preferences,
            "expected_meals_per_day": expected_meals_per_day
        }).eq("id", user.user.id).execute()


def save_recipe(recipe_id):
    """Add a recipe to the user's saved recipes list."""
    user = get_current_user()
    if user and getattr(user, 'user', None):
        try:
            # saved_recipes acts as a relation between the current user and a recipe.
            supabase.table("saved_recipes").insert({
                "user_id": user.user.id,
                "recipe_id": recipe_id
            }).execute()
            # Refresh cached saved recipes so the UI shows the saved state immediately.
            get_saved_recipes.clear()
        except Exception:
            # Ignore duplicate saves or temporary database errors in the UI flow.
            # This keeps the button interaction from crashing the page.
            pass 


def remove_saved_recipe(recipe_id):
    """Remove a recipe from the user's saved recipes list."""
    user = get_current_user()
    if user and getattr(user, 'user', None):
        # Match on both user_id and recipe_id so one user cannot remove another user's save.
        supabase.table("saved_recipes").delete().eq("user_id", user.user.id).eq("recipe_id", recipe_id).execute()
        # Clear the cached list so the removed recipe disappears from the UI.
        get_saved_recipes.clear()


def mark_recipe_seen(recipe_id):
    """Store that the user has already seen this recipe recommendation."""
    user = get_current_user()
    if user and getattr(user, 'user', None):
        # The seen_recipes table helps the app avoid showing the same recommendation repeatedly.
        supabase.table("seen_recipes").insert({
            "user_id": user.user.id,
            "recipe_id": recipe_id
        }).execute()
        # Clear the cached seen list so recommendation filtering uses the latest history.
        get_seen_recipes.clear()


def mark_recipe_cooked(recipe_id):
    """Store that the user cooked this recipe."""
    user = get_current_user()
    if user and getattr(user, 'user', None):
        # cooked_recipes is used for history and for nutrition tracking over time.
        supabase.table("cooked_recipes").insert({
            "user_id": user.user.id,
            "recipe_id": recipe_id
        }).execute()
        # Clear the cached cooked list so dashboards and nutrition summaries update.
        get_cooked_recipes.clear()


@st.cache_data(ttl=60)
def get_saved_recipes():
    """Return the user's saved recipes, newest first."""
    user = get_current_user()
    if user and getattr(user, 'user', None):
        # Newest first makes saved recipes appear in the order the user most recently saved them.
        res = supabase.table("saved_recipes").select("*").eq("user_id", user.user.id).order("saved_at", desc=True).execute()
        return res.data
    return []


@st.cache_data(ttl=60)
def get_seen_recipes():
    """Return the user's recently seen recipes for recommendation filtering."""
    user = get_current_user()
    if user and getattr(user, 'user', None):
        # Only the most recent seen items are needed, so the query is limited to keep it light.
        res = supabase.table("seen_recipes").select("*").eq("user_id", user.user.id).order("seen_at", desc=True).limit(50).execute()
        return res.data
    return []


@st.cache_data(ttl=60)
def get_cooked_recipes():
    """Return the recipes the user has marked as cooked, newest first."""
    user = get_current_user()
    if user and getattr(user, 'user', None):
        # Newest cooked recipes are returned first for history views and recent nutrition summaries.
        res = supabase.table("cooked_recipes").select("*").eq("user_id", user.user.id).order("cooked_at", desc=True).execute()
        return res.data
    return []
