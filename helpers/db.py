import sqlite3
import pandas as pd
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "recipes.db")

def get_connection():
    return sqlite3.connect(DB_PATH)

def search_recipes(query, limit=50):
    query = query.strip()
    with get_connection() as conn:
        if not query:
            # return random or top limit
            return pd.read_sql("SELECT recipe_id, recipe_title, est_prep_time_min, est_cook_time_min, main_ingredient FROM recipes LIMIT ?", conn, params=(limit,)).to_dict(orient="records")
            
        sql = """
            SELECT DISTINCT r.recipe_id, r.recipe_title, r.est_prep_time_min, r.est_cook_time_min, r.main_ingredient
            FROM recipes r
            LEFT JOIN recipe_ingredients ri ON r.recipe_id = ri.recipe_id
            LEFT JOIN ingredients i ON ri.ingredient_id = i.ingredient_id
            WHERE r.recipe_title LIKE ? OR i.original_string LIKE ? OR i.pure_ingredient_harsh LIKE ?
            LIMIT ?
        """
        like_query = f"%{query}%"
        df = pd.read_sql(sql, conn, params=(like_query, like_query, like_query, limit))
        return df.to_dict(orient="records")

def get_recipe_by_id(recipe_id):
    with get_connection() as conn:
        sql = "SELECT * FROM recipes WHERE recipe_id = ?"
        df = pd.read_sql(sql, conn, params=(recipe_id,))
        if df.empty:
            return None
        return df.iloc[0].to_dict()

def get_ingredients_for_recipe(recipe_id):
    with get_connection() as conn:
        sql = """
            SELECT i.*, ri.*
            FROM ingredients i
            JOIN recipe_ingredients ri ON i.ingredient_id = ri.ingredient_id
            WHERE ri.recipe_id = ?
        """
        df = pd.read_sql(sql, conn, params=(recipe_id,))
        return df.to_dict(orient="records")

def search_recipes_by_ingredients(ingredients_list, limit=10):
    if not ingredients_list:
        return []
    with get_connection() as conn:
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
        return df.to_dict(orient="records")
