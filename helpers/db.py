import pandas as pd
import os
import streamlit as st
from helpers.supabase_client import supabase

@st.cache_data(ttl=3600)
def search_recipes(query, limit=50, max_time=None, min_time=None, difficulty=None, dietary_prefs=None, cooking_prefs=None):
    """
    Searches recipes on Supabase using Full-Text Search and filters.
    """
    query = query.strip()
    
    # Start building the query
    q = supabase.table("recipes").select("*")
    
    # 1. Basic Filters
    if difficulty and difficulty != "Any":
        q = q.eq('difficulty', difficulty)
        
    if max_time:
        q = q.lte('est_prep_time_min', max_time)
        
    # 2. Dietary Restrictions
    if dietary_prefs:
        for pref in dietary_prefs:
            col_name = f"is_{pref.lower().replace('-', '_')}"
            q = q.eq(col_name, True)
            
    # 3. Cooking Preferences (Tastes)
    if cooking_prefs:
        for pref in cooking_prefs:
            if pref in ["Spicy", "Sweet", "Savory", "Umami"]:
                q = q.or_(f"primary_taste.eq.{pref},secondary_taste.eq.{pref}")
            elif pref == "Fast":
                q = q.eq("cook_speed", "Fast")
            elif pref == "Slow":
                q = q.eq("cook_speed", "Slow")
            elif pref == "Easy":
                q = q.eq("difficulty", "Easy")
            elif pref == "Hard":
                q = q.eq("difficulty", "Hard")

    # Apply limit
    q = q.limit(limit)
    
    # 4. Full-Text Search MUST be applied last because it returns a SyncQueryRequestBuilder
    # which does not support further method chaining for filters/limits in this version of the client.
    if query:
        q = q.text_search('fts', query)

    res = q.execute()
    return deduplicate_recipes(res.data or [])

def deduplicate_recipes(recipes):
    """
    Deduplicates a list of recipe dictionaries by recipe_id and then by recipe_title (case-insensitive).
    """
    unique_recipes = []
    seen_ids = set()
    seen_titles = set()
    
    for recipe in recipes:
        recipe_id = recipe.get('recipe_id')
        recipe_title = str(recipe.get('recipe_title', '')).strip().lower()
        
        if recipe_id not in seen_ids and recipe_title not in seen_titles:
            unique_recipes.append(recipe)
            seen_ids.add(recipe_id)
            if recipe_title:
                seen_titles.add(recipe_title)
            
    return unique_recipes

@st.cache_data(ttl=3600)
def get_recipe_by_id(recipe_id):
    res = supabase.table("recipes").select("*").eq("recipe_id", recipe_id).execute()
    return res.data[0] if res.data else None

@st.cache_data(ttl=3600)
def get_ingredients_for_recipe(recipe_id):
    # Fetch from the junction table and ingredients table
    res = supabase.table("recipe_ingredients")\
        .select("*, ingredients(*)")\
        .eq("recipe_id", recipe_id)\
        .execute()
    
    # Flatten the result to match the old format
    flattened = []
    for item in (res.data or []):
        ing = item.get("ingredients") or {}
        # Merge junction data (if any) with ingredient data
        combined = {**ing, **item}
        flattened.append(combined)
    return flattened

@st.cache_data(ttl=3600)
def search_recipes_by_ingredients(ingredients_list, limit=12, dietary_prefs=None, cooking_prefs=None):
    if not ingredients_list:
        return []
    
    # Use the RPC function we created on Supabase
    params = {
        "search_ingredients": ingredients_list,
        "row_limit": limit,
        "dietary_vegan": True if "Vegan" in (dietary_prefs or []) else None,
        "dietary_vegetarian": True if "Vegetarian" in (dietary_prefs or []) else None,
        "dietary_gluten_free": True if "Gluten-Free" in (dietary_prefs or []) else None,
        "dietary_dairy_free": True if "Dairy-Free" in (dietary_prefs or []) else None,
        "dietary_nut_free": True if "Nut-Free" in (dietary_prefs or []) else None,
        "dietary_halal": True if "Halal" in (dietary_prefs or []) else None,
        "dietary_kosher": True if "Kosher" in (dietary_prefs or []) else None,
        "pref_spicy": True if "Spicy" in (cooking_prefs or []) else None,
        "pref_sweet": True if "Sweet" in (cooking_prefs or []) else None,
        "pref_savory": True if "Savory" in (cooking_prefs or []) else None,
        "pref_umami": True if "Umami" in (cooking_prefs or []) else None,
        "pref_fast": True if "Fast" in (cooking_prefs or []) else None,
        "pref_slow": True if "Slow" in (cooking_prefs or []) else None,
        "pref_easy": True if "Easy" in (cooking_prefs or []) else None,
        "pref_hard": True if "Hard" in (cooking_prefs or []) else None,
    }
    
    res = supabase.rpc("search_recipes_by_ingredients", params).execute()
    return deduplicate_recipes(res.data or [])
