import pandas as pd
import numpy as np
import streamlit as st
from helpers.db import deduplicate_recipes
from helpers.supabase_client import get_saved_recipes, get_cooked_recipes, supabase

@st.cache_data(ttl=86400)
def load_base_features():
    """Loads a simplified version of the recipes table for feature matching once from Supabase."""
    res = supabase.table("recipes").select("""
        recipe_id, recipe_title, est_prep_time_min, est_cook_time_min, 
        difficulty, is_vegan, is_vegetarian, is_gluten_free, is_dairy_free, is_nut_free, is_halal, is_kosher,
        primary_taste, cook_speed
    """).execute()
    
    df = pd.DataFrame(res.data or [])
    
    if df.empty:
        return df
        
    df['difficulty_num'] = df['difficulty'].map({'Easy': 1, 'Medium': 2, 'Hard': 3}).fillna(1)
    df['total_time'] = df['est_prep_time_min'].fillna(0) + df['est_cook_time_min'].fillna(0)
    
    # Map tastes to numeric features
    tastes = ["Spicy", "Sweet", "Savory", "Umami"]
    for t in tastes:
        df[f'is_{t.lower()}'] = (df['primary_taste'] == t).astype(int)

    df['is_fast'] = (df['cook_speed'] == 'Fast').astype(int)
    df['is_slow'] = (df['cook_speed'] == 'Slow').astype(int)

    features = ['total_time', 'difficulty_num', 'is_vegan', 'is_vegetarian', 'is_gluten_free', 
                'is_dairy_free', 'is_nut_free', 'is_halal', 'is_kosher', 'is_fast', 'is_slow'] + [f'is_{t.lower()}' for t in tastes]
    
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
    """Re-calculates recommendations incorporating both history and profile preferences."""
    from helpers.supabase_client import get_profile
    
    saved = get_saved_recipes()
    cooked = get_cooked_recipes()
    profile = get_profile()
    
    user_recipe_ids = set()
    for item in saved:
        user_recipe_ids.add(str(item.get("recipe_id")))
    for item in cooked:
        user_recipe_ids.add(str(item.get("recipe_id")))
        
    # Load normalized base features (cached)
    df = load_base_features()
    
    if df.empty:
        return []
        
    tastes = ["Spicy", "Sweet", "Savory", "Umami"]
    features = ['total_time', 'difficulty_num', 'is_vegan', 'is_vegetarian', 'is_gluten_free', 
                'is_dairy_free', 'is_nut_free', 'is_halal', 'is_kosher', 'is_fast', 'is_slow'] + [f'is_{t.lower()}' for t in tastes]
    
    # 1. Base User Profile from history
    user_mask = df['recipe_id_str'].isin(user_recipe_ids)
    user_df = df[user_mask]
    
    if user_df.empty:
        # If no history, start with a "neutral" profile
        user_profile = pd.Series(0.0, index=features)
    else:
        user_profile = user_df[features].mean()

    # 2. Inject explicit preferences from profile
    if profile:
        dietary = profile.get("dietary_restrictions", [])
        cooking = profile.get("cooking_preferences", [])
        
        # Dietary restrictions are "hard" requirements (boost them to max)
        for d in dietary:
            feat_name = f"is_{d.lower().replace('-', '_')}"
            if feat_name in user_profile:
                user_profile[feat_name] = 1.5 # Extra weight for explicit requirements
        
        # Cooking preferences (tastes, speed, difficulty)
        for c in cooking:
            feat_name = f"is_{c.lower()}"
            if feat_name in user_profile:
                user_profile[feat_name] = 1.2 # Boost for preferred tastes
            elif c == "Fast":
                user_profile['is_fast'] = 1.2
            elif c == "Slow":
                user_profile['is_slow'] = 1.2
            elif c == "Easy":
                user_profile['difficulty_num'] = 0.0 # Easy is 0 after normalization if min is Easy
            elif c == "Hard":
                user_profile['difficulty_num'] = 1.0 # Hard is 1 after normalization if max is Hard

    # 3. Calculate distance to target recipes (excluding ones already cooked/saved)
    target_df = df[~user_mask].copy()
    
    if target_df.empty:
        return []
        
    distances = np.sqrt(((target_df[features] - user_profile) ** 2).sum(axis=1))
    target_df['distance'] = distances
    
    # Get a bit more than limit to allow for deduplication
    recommended = target_df.sort_values('distance').head(limit * 2)
    recipes = recommended.to_dict(orient="records")
    return deduplicate_recipes(recipes)[:limit]
