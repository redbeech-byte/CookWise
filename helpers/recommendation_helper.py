import pandas as pd
import numpy as np
import streamlit as st
from helpers.db import get_connection, deduplicate_recipes
from helpers.supabase_client import get_saved_recipes, get_cooked_recipes

@st.cache_data(ttl=86400)
def load_base_features():
    """Loads a simplified version of the recipes table for feature matching once."""
    conn = get_connection()
    df = pd.read_sql("""
        SELECT recipe_id, recipe_title, est_prep_time_min, est_cook_time_min, 
               difficulty, is_vegan, is_vegetarian, is_gluten_free
        FROM recipes
    """, conn)
    
    if df.empty:
        return df
        
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
    return df

@st.cache_data(ttl=600)
def get_recommended_recipes(limit=10):
    """Re-calculates recommendations but caches them for 10 mins or until user_recipe_ids change."""
    saved = get_saved_recipes()
    cooked = get_cooked_recipes()
    
    user_recipe_ids = set()
    for item in saved:
        user_recipe_ids.add(str(item.get("recipe_id")))
    for item in cooked:
        user_recipe_ids.add(str(item.get("recipe_id")))
        
    # Load normalized base features (cached)
    df = load_base_features()
    
    if df.empty:
        return []
        
    if not user_recipe_ids:
        # Fallback to top recipes
        return df.head(limit).to_dict(orient="records")
        
    features = ['total_time', 'difficulty_num', 'is_vegan', 'is_vegetarian', 'is_gluten_free']
    user_mask = df['recipe_id_str'].isin(user_recipe_ids)
    
    user_df = df[user_mask]
    target_df = df[~user_mask]
    
    if user_df.empty or target_df.empty:
        return target_df.head(limit).to_dict(orient="records")
        
    # Calculate user profile
    user_profile = user_df[features].mean()
    
    # Calculate distance
    distances = np.sqrt(((target_df[features] - user_profile) ** 2).sum(axis=1))
    
    target_df = target_df.copy()
    target_df['distance'] = distances
    
    # Get a bit more than limit to allow for deduplication
    recommended = target_df.sort_values('distance').head(limit * 2)
    recipes = recommended.to_dict(orient="records")
    return deduplicate_recipes(recipes)[:limit]
