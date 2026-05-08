import streamlit as st
from supabase import create_client, Client

# Storing the public Supabase project configuration used by the client app.
# These values connect the app to the correct Supabase project.
SUPABASE_URL = "https://oztujhafgvuaowznmzql.supabase.co"
SUPABASE_KEY = "sb_publishable_Ny6S6HQCCOoiVP-t8IWttA_bt3B8WiY"


@st.cache_resource
def init_supabase() -> Client:
    # Creating the Supabase client once and reusing it across reruns.
    # `cache_resource` is used here because the client is a long-lived connection-style object.
    return create_client(SUPABASE_URL, SUPABASE_KEY)


# Initializing one shared Supabase client for this Streamlit session.
supabase: Client = init_supabase()


@st.cache_data(ttl=3600)
def get_vault_secrets():
    """
    Retrieving sensitive API keys from Supabase Vault.
    This call requires authentication to succeed.
    """
    try:
        res = supabase.rpc("get_secrets").execute()

        # Converting the returned rows into a simple {name: secret} dictionary.
        # This makes later secret lookups easier in the rest of the app.
        secrets_dict = {item['name']: item['secret'] for item in res.data}
        return secrets_dict
    except Exception as e:
        # Returning an empty dictionary if Vault access fails.
        # This prevents the app from crashing immediately and exposes a readable error.
        st.error(f"Failed to load secrets from Vault: {e}")
        return {}


def get_current_user():
    # Returning the currently authenticated Supabase user session.
    return supabase.auth.get_user()


def login(email, password):
    # Sending email/password credentials to Supabase authentication.
    return supabase.auth.sign_in_with_password({"email": email, "password": password})


def signup(email, password, username):
    # Creating a new account and storing the username inside user metadata.
    # That metadata is later used when creating or displaying the profile.
    return supabase.auth.sign_up({
        "email": email,
        "password": password,
        "options": {
            "data": {"username": username}
        }
    })


def logout():
    # Clearing session state and cached user-related data before signing out.
    # This helps prevent old user data from lingering after logout.
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.cache_data.clear()

    return supabase.auth.sign_out()


def update_password(new_password):
    # Updating the password for the currently authenticated user.
    return supabase.auth.update_user({"password": new_password})


def delete_account():
    # Deleting the user's profile row and then logging the user out.
    # Full account deletion in Supabase Auth usually needs admin privileges or re-authentication,
    # so this function mainly removes app-level profile data.
    user = get_current_user()
    if user and getattr(user, 'user', None):
        user_id = user.user.id

        # Removing the matching user profile from the app database.
        supabase.table("user_profiles").delete().eq("id", user_id).execute()

        # Logging out afterward so the local app session is cleared as well.
        return logout()


# --- Database helpers ---

def get_profile():
    # Loading the profile row for the currently authenticated user.
    user = get_current_user()
    if not user or not getattr(user, 'user', None):
        return None

    user_id = user.user.id
    res = supabase.table("user_profiles").select("*").eq("id", user_id).execute()

    if not res.data:
        # Self-healing behavior: if the auth user exists but the profile row is missing,
        # create a basic profile automatically instead of leaving the app in a broken state.
        username = user.user.user_metadata.get("username", "Chef")
        try:
            supabase.table("user_profiles").insert({
                "id": user_id,
                "username": username
            }).execute()

            # Retrying the fetch after creating the missing profile row.
            res = supabase.table("user_profiles").select("*").eq("id", user_id).execute()
        except Exception as e:
            # Returning None if profile recovery fails.
            st.error(f"Failed to create missing profile: {e}")
            return None

    # Returning the first profile row because each user should have only one profile.
    return res.data[0] if res.data else None


def update_profile(dietary_restrictions, cooking_preferences, expected_meals_per_day=3):
    # Updating editable preference fields for the current user's profile.
    user = get_current_user()
    if user and getattr(user, 'user', None):
        supabase.table("user_profiles").update({
            "dietary_restrictions": dietary_restrictions,
            "cooking_preferences": cooking_preferences,
            "expected_meals_per_day": expected_meals_per_day
        }).eq("id", user.user.id).execute()


def save_recipe(recipe_id):
    # Saving a recipe to the user's saved-recipes list.
    user = get_current_user()
    if user and getattr(user, 'user', None):
        try:
            supabase.table("saved_recipes").insert({
                "user_id": user.user.id,
                "recipe_id": recipe_id
            }).execute()

            # Clearing the cached saved-recipes query so the UI refreshes with the new data.
            get_saved_recipes.clear()
        except Exception:
            # Silently ignoring insert failures here.
            # This likely avoids breaking the UI for duplicate saves or minor backend issues,
            # though it also hides the exact reason for failure.
            pass


def remove_saved_recipe(recipe_id):
    # Removing one saved recipe relation for the current user.
    user = get_current_user()
    if user and getattr(user, 'user', None):
        supabase.table("saved_recipes").delete().eq("user_id", user.user.id).eq("recipe_id", recipe_id).execute()
        get_saved_recipes.clear()


def mark_recipe_seen(recipe_id):
    # Recording that the user has viewed a recipe.
    # This history can later support recommendation logic or UI behavior.
    user = get_current_user()
    if user and getattr(user, 'user', None):
        supabase.table("seen_recipes").insert({
            "user_id": user.user.id,
            "recipe_id": recipe_id
        }).execute()
        get_seen_recipes.clear()


def mark_recipe_cooked(recipe_id):
    # Recording that the user cooked a recipe.
    # This history is important for nutrition tracking and recommendation logic.
    user = get_current_user()
    if user and getattr(user, 'user', None):
        supabase.table("cooked_recipes").insert({
            "user_id": user.user.id,
            "recipe_id": recipe_id
        }).execute()
        get_cooked_recipes.clear()


@st.cache_data(ttl=60)
def get_saved_recipes():
    # Loading the current user's saved recipes and caching the result briefly.
    # A short TTL reduces repeated Supabase calls during Streamlit reruns.
    user = get_current_user()
    if user and getattr(user, 'user', None):
        res = supabase.table("saved_recipes").select("*").eq("user_id", user.user.id).order("saved_at", desc=True).execute()
        return res.data
    return []


@st.cache_data(ttl=60)
def get_seen_recipes():
    # Loading recently seen recipes for the current user.
    # The result is limited to 50 rows to keep this history lighter.
    user = get_current_user()
    if user and getattr(user, 'user', None):
        res = supabase.table("seen_recipes").select("*").eq("user_id", user.user.id).order("seen_at", desc=True).limit(50).execute()
        return res.data
    return []


@st.cache_data(ttl=60)
def get_cooked_recipes():
    # Loading the user's cooked-recipe history.
    # This data feeds features like nutrition tracking and history displays.
    user = get_current_user()
    if user and getattr(user, 'user', None):
        res = supabase.table("cooked_recipes").select("*").eq("user_id", user.user.id).order("cooked_at", desc=True).execute()
        return res.data
    return []
