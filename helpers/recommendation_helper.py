import pandas as pd
import numpy as np
from helpers.db import get_connection
from helpers.supabase_client import get_saved_recipes, get_cooked_recipes

def get_recommended_recipes(limit=10):
    saved = get_saved_recipes()
    cooked = get_cooked_recipes()
    
    user_recipe_ids = set()
    for item in saved:
        user_recipe_ids.add(str(item.get("recipe_id")))
    for item in cooked:
        user_recipe_ids.add(str(item.get("recipe_id")))
        
    with get_connection() as conn:
        df = pd.read_sql("""
            SELECT recipe_id, recipe_title, est_prep_time_min, est_cook_time_min, 
                   difficulty, is_vegan, is_vegetarian, is_gluten_free
            FROM recipes
        """, conn)
        
    if df.empty:
        return []
        
    if not user_recipe_ids:
        # Fallback
        return df.head(limit).to_dict(orient="records")
        
    df['difficulty_num'] = df['difficulty'].map({'Easy': 1, 'Medium': 2, 'Hard': 3}).fillna(1)
    df['total_time'] = df['est_prep_time_min'].fillna(0) + df['est_cook_time_min'].fillna(0)
    
    features = ['total_time', 'difficulty_num', 'is_vegan', 'is_vegetarian', 'is_gluten_free']
    for f in features:
        df[f] = pd.to_numeric(df[f], errors='coerce').fillna(0)
        
    # Min-max normalization
    for f in features:
        max_val = df[f].max()
        min_val = df[f].min()
        if max_val > min_val:
            df[f] = (df[f] - min_val) / (max_val - min_val)
            
    df['recipe_id_str'] = df['recipe_id'].astype(str)
    user_mask = df['recipe_id_str'].isin(user_recipe_ids)
    
    user_df = df[user_mask]
    target_df = df[~user_mask]
    
    if user_df.empty or target_df.empty:
        # Just return top 
        return target_df.head(limit).to_dict(orient="records")
        
    # Calculate user profile: average of all their saved/cooked features
    user_profile = user_df[features].mean()
    
    # Calculate Euclidean distance between each candidate and the user profile
    distances = np.sqrt(((target_df[features] - user_profile) ** 2).sum(axis=1))
    
    target_df = target_df.copy()
    target_df['distance'] = distances
    
    recommended = target_df.sort_values('distance').head(limit)
    return recommended.to_dict(orient="records")
