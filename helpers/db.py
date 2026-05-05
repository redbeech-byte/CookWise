import sqlite3
import pandas as pd
import os
import streamlit as st

# Robust absolute path for the database file
HELPERS_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.normpath(os.path.join(HELPERS_DIR, "..", "data", "recipes.db"))

@st.cache_resource
def get_connection():
    # check_same_thread=False is needed for SQLite in Streamlit's multi-threaded environment
    return sqlite3.connect(DB_PATH, check_same_thread=False)

@st.cache_data(ttl=3600)
def search_recipes(query, limit=50, max_time=None, min_time=None, difficulty=None, dietary_prefs=None):
    query = query.strip()
    conn = get_connection()
    sql = """
        SELECT DISTINCT r.recipe_id, r.recipe_title, r.est_prep_time_min, r.est_cook_time_min, r.main_ingredient, r.difficulty, r.is_vegan, r.is_vegetarian, r.is_gluten_free
        FROM recipes r
        LEFT JOIN recipe_ingredients ri ON r.recipe_id = ri.recipe_id
        LEFT JOIN ingredients i ON ri.ingredient_id = i.ingredient_id
        WHERE 1=1
    """
    
    params = []
    if query:
        sql += " AND (r.recipe_title LIKE ? OR i.original_string LIKE ? OR i.pure_ingredient_harsh LIKE ?)"
        like_query = f"%{query}%"
        params.extend([like_query, like_query, like_query])
        
    if max_time:
        sql += " AND (r.est_prep_time_min + r.est_cook_time_min) <= ?"
        params.append(max_time)

    if min_time:
        sql += " AND (r.est_prep_time_min + r.est_cook_time_min) >= ?"
        params.append(min_time)
        
    if difficulty and difficulty != "Any":
        sql += " AND r.difficulty = ?"
        params.append(difficulty)
        
    if dietary_prefs:
        for pref in dietary_prefs:
            if pref == "Vegan":
                sql += " AND r.is_vegan = 1"
            elif pref == "Vegetarian":
                sql += " AND r.is_vegetarian = 1"
            elif pref == "Gluten-Free":
                sql += " AND r.is_gluten_free = 1"
            elif pref == "Dairy-Free":
                sql += " AND r.is_dairy_free = 1"
            elif pref == "Nut-Free":
                sql += " AND r.is_nut_free = 1"
    
    sql += " LIMIT ?"
    params.append(limit)
    
    df = pd.read_sql(sql, conn, params=tuple(params))
    recipes = df.to_dict(orient="records")
    return deduplicate_recipes(recipes)

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
    conn = get_connection()
    sql = "SELECT * FROM recipes WHERE recipe_id = ?"
    df = pd.read_sql(sql, conn, params=(recipe_id,))
    if df.empty:
        return None
    return df.iloc[0].to_dict()

@st.cache_data(ttl=3600)
def get_ingredients_for_recipe(recipe_id):
    conn = get_connection()
    sql = """
        SELECT i.*, ri.*
        FROM ingredients i
        JOIN recipe_ingredients ri ON i.ingredient_id = ri.ingredient_id
        WHERE ri.recipe_id = ?
    """
    df = pd.read_sql(sql, conn, params=(recipe_id,))
    return df.to_dict(orient="records")

@st.cache_data(ttl=3600)
def search_recipes_by_ingredients(ingredients_list, limit=10):
    if not ingredients_list:
        return []
    conn = get_connection()
    placeholders = " OR ".join(["i.pure_ingredient_harsh LIKE ? OR i.original_string LIKE ?"] * len(ingredients_list))
    params = []
    for ing in ingredients_list:
        params.extend([f"%{ing.lower()}%", f"%{ing.lower()}%"])
        
    sql = f"""
        SELECT r.recipe_id, r.recipe_title, r.est_prep_time_min, r.est_cook_time_min, r.main_ingredient, COUNT(DISTINCT i.ingredient_id) as match_count
        FROM recipes r
        JOIN recipe_ingredients ri ON r.recipe_id = ri.recipe_id
        JOIN ingredients i ON ri.ingredient_id = i.ingredient_id
        WHERE {placeholders}
        GROUP BY r.recipe_id
        ORDER BY match_count DESC
        LIMIT ?
    """
    params.append(limit)
    df = pd.read_sql(sql, conn, params=params)
    recipes = df.to_dict(orient="records")
    return deduplicate_recipes(recipes)
