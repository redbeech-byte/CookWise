import pandas as pd
import os
import streamlit as st
from helpers.supabase_client import supabase

@st.cache_data(ttl=3600)
def search_recipes(query, limit=50, max_time=None, min_time=None, difficulty=None, dietary_prefs=None, cooking_prefs=None):
    # Searching recipes on Supabase using a mix of direct filters and full-text search.
    # The result is cached because search pages can rerun often in Streamlit.
    query = query.strip()
    
    # Starting with the recipes table keeps the query flexible before filters are added.
    q = supabase.table("recipes").select("*")
    
    # Applying basic filters first narrows the recipe set before text search is added.
    if difficulty and difficulty != "Any":
        q = q.eq('difficulty', difficulty)
        
    if max_time:
        q = q.lte('est_prep_time_min', max_time)
        
    # Dietary preferences map directly to boolean columns such as is_vegan or
    # is_gluten_free, so each selected preference becomes a required filter.
    if dietary_prefs:
        for pref in dietary_prefs:
            col_name = f"is_{pref.lower().replace('-', '_')}"
            q = q.eq(col_name, True)
            
    # Cooking preferences include both taste labels and practical choices like
    # speed or difficulty, so each option maps to the matching recipe column.
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

    # Limiting the number of rows keeps the search response lightweight for the UI.
    q = q.limit(limit)
    
    # Full-text search is applied last because this Supabase client version returns
    # a builder that does not support more filter/limit chaining afterward.
    if query:
        q = q.text_search('fts', query)

    res = q.execute()
    return deduplicate_recipes(res.data or [])

def deduplicate_recipes(recipes):
    # Removing duplicates by recipe_id first and recipe_title second.
    # The title check catches cases where the same recipe appears with different ids
    # or from joined/search results that repeat similar rows.
    unique_recipes = []
    seen_ids = set()
    seen_titles = set()
    
    for recipe in recipes:
        recipe_id = recipe.get('recipe_id')
        # Normalizing the title makes duplicate detection case-insensitive and ignores
        # extra spaces at the beginning or end.
        recipe_title = str(recipe.get('recipe_title', '')).strip().lower()
        
        if recipe_id not in seen_ids and recipe_title not in seen_titles:
            unique_recipes.append(recipe)
            seen_ids.add(recipe_id)
            if recipe_title:
                seen_titles.add(recipe_title)
            
    return unique_recipes

@st.cache_data(ttl=3600)
def get_recipe_by_id(recipe_id):
    # Fetching one recipe row by its id for detail pages and helper functions.
    res = supabase.table("recipes").select("*").eq("recipe_id", recipe_id).execute()
    return res.data[0] if res.data else None

@st.cache_data(ttl=3600)
def get_ingredients_for_recipe(recipe_id):
    # Fetching from the junction table and the ingredients table because recipe
    # ingredients are stored as a many-to-many relationship.
    res = supabase.table("recipe_ingredients")\
        .select("*, ingredients(*)")\
        .eq("recipe_id", recipe_id)\
        .execute()
    
    # Flattening the joined result keeps the output compatible with older helper
    # code that expects ingredient fields in one dictionary.
    for item in (res.data or []):
        ing = item.get("ingredients") or {}
        # Merging junction data with ingredient data preserves both the recipe-specific
        # link information and the ingredient details.
        combined = {**ing, **item}
        flattened.append(combined)
    return flattened

@st.cache_data(ttl=3600)
def search_recipes_by_ingredients(ingredients_list, limit=12, dietary_prefs=None, cooking_prefs=None):
    # Searching by ingredients is handled by a Supabase RPC because the matching
    # logic is more complex than a simple table filter.
    if not ingredients_list:
        # Returning no results for an empty ingredient list avoids an unnecessary
        # database call and prevents unclear recommendations.
        return []
    
    # Passing None for unselected preferences lets the RPC ignore those filters.
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
    
    # The RPC returns candidate recipes based on ingredient overlap and optional
    # dietary/cooking filters.
    res = supabase.rpc("search_recipes_by_ingredients", params).execute()
    return deduplicate_recipes(res.data or [])
