import pandas as pd
import numpy as np
import streamlit as st
from sklearn.neighbors import NearestNeighbors
from sklearn.feature_extraction.text import TfidfVectorizer
from helpers.db import deduplicate_recipes
from helpers.supabase_client import get_saved_recipes, get_cooked_recipes, supabase

@st.cache_data(ttl=86400)
def load_base_features():
    """Loads an extended version of the recipes table for feature matching using KNN, including TF-IDF ingredients."""
    res = supabase.table("recipes").select("""
        recipe_id, recipe_title, est_prep_time_min, est_cook_time_min, 
        difficulty, is_vegan, is_vegetarian, is_gluten_free, is_dairy_free, is_nut_free, is_halal, is_kosher,
        primary_taste, cook_speed, num_ingredients, num_steps, main_ingredient,
        recipe_ingredients(ingredients(pure_ingredient_harsh))
    """).execute()
    
    df = pd.DataFrame(res.data or [])
    
    if df.empty:
        return df, []
        
    # Extract ingredient text for TF-IDF Vectorization
    ingredient_texts = []
    for row in res.data:
        ings = []
        for ri in row.get('recipe_ingredients', []):
            ing_data = ri.get('ingredients')
            if ing_data:
                ing_name = ing_data.get('pure_ingredient_harsh')
                if ing_name:
                    ings.append(ing_name)
        ingredient_texts.append(" ".join(ings))
        
    df['ingredient_text'] = ingredient_texts
        
    # Map categorical info to numbers
    df['difficulty_num'] = df['difficulty'].map({'Easy': 1, 'Medium': 2, 'Hard': 3}).fillna(1)
    df['total_time'] = df['est_prep_time_min'].fillna(0) + df['est_cook_time_min'].fillna(0)
    
    # Clean data & calculate median for missing values
    df['num_ingredients'] = df['num_ingredients'].fillna(df['num_ingredients'].median())
    df['num_steps'] = df['num_steps'].fillna(df['num_steps'].median())
    
    # Map tastes to numeric features
    tastes = ["Spicy", "Sweet", "Savory", "Umami"]
    for t in tastes:
        df[f'is_{t.lower()}'] = (df['primary_taste'] == t).astype(int)

    df['is_fast'] = (df['cook_speed'] == 'Fast').astype(int)
    df['is_slow'] = (df['cook_speed'] == 'Slow').astype(int)

    # Encode main ingredients as boolean columns
    main_ings = ['poultry', 'red_meat', 'seafood', 'plant', 'egg_dairy']
    for ing in main_ings:
        df[f'main_{ing}'] = (df['main_ingredient'] == ing).astype(int)

    base_features = ['total_time', 'difficulty_num', 'num_ingredients', 'num_steps',
                'is_vegan', 'is_vegetarian', 'is_gluten_free', 'is_dairy_free', 
                'is_nut_free', 'is_halal', 'is_kosher', 'is_fast', 'is_slow'] + \
                [f'is_{t.lower()}' for t in tastes] + \
                [f'main_{ing}' for ing in main_ings]
    
    for f in base_features:
        df[f] = pd.to_numeric(df[f], errors='coerce').fillna(0).astype(float)
        
    # Min-max normalization for basic numerical features
    for f in base_features:
        max_val = df[f].max()
        min_val = df[f].min()
        if max_val > min_val:
            df[f] = (df[f] - min_val) / (max_val - min_val)
            
    # Apply TF-IDF for ingredients (keep to top 150 important flavors to prevent overfitting)
    tfidf = TfidfVectorizer(max_features=150, stop_words='english')
    tfidf_matrix = tfidf.fit_transform(df['ingredient_text'])
    
    # Store TF-IDF as columns
    tfidf_feature_names = [f"tfidf_{w}" for w in tfidf.get_feature_names_out()]
    tfidf_df = pd.DataFrame(tfidf_matrix.toarray(), columns=tfidf_feature_names)
    
    # Combine TF-IDF dataframe with our main working dataframe
    df = pd.concat([df, tfidf_df], axis=1)
    
    features = base_features + tfidf_feature_names
    
    df['recipe_id_str'] = df['recipe_id'].astype(str)
    return df, features

@st.cache_data(ttl=600)
def get_recommended_recipes(limit=10):
    """Calculates recommendations using K-Nearest Neighbors based on history and profile preferences."""
    from helpers.supabase_client import get_profile
    
    saved = get_saved_recipes() or []
    cooked = get_cooked_recipes() or []
    profile = get_profile()
    
    user_recipe_ids = set()
    for item in saved:
        user_recipe_ids.add(str(item.get("recipe_id")))
    for item in cooked:
        user_recipe_ids.add(str(item.get("recipe_id")))
        
    # Load normalized base features (cached)
    loaded = load_base_features()
    if len(loaded) != 2 or (isinstance(loaded[0], pd.DataFrame) and loaded[0].empty):
        return []
        
    df, features = loaded
    
    # 1. Base User Profile from history
    user_mask = df['recipe_id_str'].isin(user_recipe_ids)
    user_df = df[user_mask]
    
    if user_df.empty:
        # If no history, start with a "neutral" profile
        user_profile = pd.Series(0.0, index=features)
    else:
        user_profile = user_df[features].mean()

    # 2. Inject explicit preferences from profile to strongly influence KNN weights
    #Fall back to [] if profile is None to avoid errors
    if profile:
        dietary = profile.get("dietary_restrictions") or []
        cooking = profile.get("cooking_preferences") or []
        
        # Dietary restrictions are "hard" requirements in KNN space, drastically shift the target vector
        for d in dietary:
            feat_name = f"is_{d.lower().replace('-', '_')}"
            if feat_name in user_profile:
                # Strong weighting to push the nearest neighbor calculation towards these specific features.
                user_profile[feat_name] = 5.0 
        
        # Cooking preferences (tastes, speed, difficulty)
        for c in cooking:
            feat_name = f"is_{c.lower()}"
            if feat_name in user_profile:
                user_profile[feat_name] = 1.5 
            elif c == "Fast":
                user_profile['is_fast'] = 1.5
            elif c == "Slow":
                user_profile['is_slow'] = 1.5
            elif c == "Easy":
                user_profile['difficulty_num'] = 0.0 # Push towards 0 (normalized Easy)
            elif c == "Hard":
                user_profile['difficulty_num'] = 1.0 # Push towards 1 (normalized Hard)

    # 3. Calculate closest neighbors in the feature space
    target_df = df[~user_mask].copy()
    
    if target_df.empty:
        return []
        
    # Fit the KNN model
    X = target_df[features].values
    k_neighbors = min(limit * 2, len(target_df))
    knn_model = NearestNeighbors(n_neighbors=k_neighbors, algorithm='auto', metric='euclidean')
    knn_model.fit(X)
    
    # Find the nearest items to our idealized user profile target vector
    distances, indices = knn_model.kneighbors([user_profile.values])
    
    # Retrieve top recommended records
    recommended = target_df.iloc[indices[0]]
    recipes = recommended.to_dict(orient="records")
    return deduplicate_recipes(recipes)[:limit]
