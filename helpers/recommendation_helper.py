import pandas as pd
import numpy as np
import streamlit as st
from sklearn.neighbors import NearestNeighbors
from sklearn.feature_extraction.text import TfidfVectorizer
from helpers.db import deduplicate_recipes
from helpers.supabase_client import get_saved_recipes, get_cooked_recipes, supabase


@st.cache_data(ttl=86400)
def load_base_features():
    """Loading an extended recipe feature table for recommendation matching."""
    # Pulling recipe metadata plus linked ingredient names from Supabase.
    # This becomes the base dataset for similarity matching.
    res = supabase.table("recipes").select("""
        recipe_id, recipe_title, est_prep_time_min, est_cook_time_min, 
        difficulty, is_vegan, is_vegetarian, is_gluten_free, is_dairy_free, is_nut_free, is_halal, is_kosher,
        primary_taste, cook_speed, num_ingredients, num_steps, main_ingredient,
        recipe_ingredients(ingredients(pure_ingredient_harsh))
    """).execute()

    df = pd.DataFrame(res.data or [])

    # Returning early if no recipe data is available.
    if df.empty:
        return df, []

    # Building one ingredient-text string per recipe for TF-IDF vectorization.
    # This lets ingredient similarity influence the recommendation model.
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

    # Converting difficulty into an ordered numeric scale so it can be used in distance calculations.
    df['difficulty_num'] = df['difficulty'].map({'Easy': 1, 'Medium': 2, 'Hard': 3}).fillna(1)

    # Combining prep time and cook time into one total-time feature.
    df['total_time'] = df['est_prep_time_min'].fillna(0) + df['est_cook_time_min'].fillna(0)

    # Filling missing structural recipe values with the column median.
    # This avoids dropping recipes just because some numeric metadata is missing.
    df['num_ingredients'] = df['num_ingredients'].fillna(df['num_ingredients'].median())
    df['num_steps'] = df['num_steps'].fillna(df['num_steps'].median())

    # Turning taste labels into boolean features.
    # KNN needs numeric features, so categorical values must be encoded first.
    tastes = ["Spicy", "Sweet", "Savory", "Umami"]
    for t in tastes:
        df[f'is_{t.lower()}'] = (df['primary_taste'] == t).astype(int)

    # Encoding cook speed as boolean features as well.
    df['is_fast'] = (df['cook_speed'] == 'Fast').astype(int)
    df['is_slow'] = (df['cook_speed'] == 'Slow').astype(int)

    # Encoding main ingredient groups into separate boolean columns.
    main_ings = ['poultry', 'red_meat', 'seafood', 'plant', 'egg_dairy']
    for ing in main_ings:
        df[f'main_{ing}'] = (df['main_ingredient'] == ing).astype(int)

    # Defining the handcrafted numeric feature set used for similarity matching.
    base_features = ['total_time', 'difficulty_num', 'num_ingredients', 'num_steps',
                'is_vegan', 'is_vegetarian', 'is_gluten_free', 'is_dairy_free',
                'is_nut_free', 'is_halal', 'is_kosher', 'is_fast', 'is_slow'] + \
                [f'is_{t.lower()}' for t in tastes] + \
                [f'main_{ing}' for ing in main_ings]

    # Coercing all base features into numeric form so distance calculations stay stable.
    for f in base_features:
        df[f] = pd.to_numeric(df[f], errors='coerce').fillna(0).astype(float)

    # Applying min-max normalization so no single feature dominates purely because of scale.
    # For example, time values would otherwise outweigh boolean features too heavily.
    for f in base_features:
        max_val = df[f].max()
        min_val = df[f].min()
        if max_val > min_val:
            df[f] = (df[f] - min_val) / (max_val - min_val)

    # Applying TF-IDF to ingredient text so ingredient similarity also shapes recommendations.
    # The feature count is capped to reduce noise and overfitting.
    tfidf = TfidfVectorizer(max_features=150, stop_words='english')
    tfidf_matrix = tfidf.fit_transform(df['ingredient_text'])

    # Storing TF-IDF scores as normal dataframe columns so they can be merged with other features.
    tfidf_feature_names = [f"tfidf_{w}" for w in tfidf.get_feature_names_out()]
    tfidf_df = pd.DataFrame(tfidf_matrix.toarray(), columns=tfidf_feature_names)

    # Combining handcrafted recipe features with TF-IDF ingredient features.
    df = pd.concat([df, tfidf_df], axis=1)

    # Keeping a single feature list so the recommendation function knows exactly which columns to use.
    features = base_features + tfidf_feature_names

    # Storing recipe IDs as strings for safer comparison with Supabase-returned values.
    # This avoids mismatches where one source gives ints and another gives strings.
    df['recipe_id_str'] = df['recipe_id'].astype(str)
    return df, features


@st.cache_data(ttl=600)
def get_recommended_recipes(limit=10):
    """Calculating recommendations with KNN using user history and profile preferences."""
    from helpers.supabase_client import get_profile

    # Loading the user's saved and cooked history.
    # `or []` prevents iterable errors if a helper unexpectedly returns None.
    saved = get_saved_recipes() or []
    cooked = get_cooked_recipes() or []
    profile = get_profile()

    # Collecting all recipe IDs the user has already interacted with.
    # These recipes become the basis for the user's taste profile.
    user_recipe_ids = set()
    for item in saved:
        user_recipe_ids.add(str(item.get("recipe_id")))
    for item in cooked:
        user_recipe_ids.add(str(item.get("recipe_id")))

    # Loading the cached full feature table.
    loaded = load_base_features()
    if len(loaded) != 2 or (isinstance(loaded[0], pd.DataFrame) and loaded[0].empty):
        return []

    df, features = loaded

    # Isolating the recipes that already belong to the user's history.
    user_mask = df['recipe_id_str'].isin(user_recipe_ids)
    user_df = df[user_mask]

    if user_df.empty:
        # Starting from a neutral feature vector if the user has no history yet.
        # This avoids breaking the recommender for first-time users.
        user_profile = pd.Series(0.0, index=features)
    else:
        # Averaging the user's past recipes into one preference vector.
        # This becomes the target point for nearest-neighbor matching.
        user_profile = user_df[features].mean()

    # Injecting explicit profile preferences after building the history-based profile.
    # This lets the recommender reflect both observed behavior and stated preferences.
    if profile:
        # Falling back to [] if the stored profile values are missing or None.
        # Prevents: 'NoneType' object is not iterable.
        dietary = profile.get("dietary_restrictions") or []
        cooking = profile.get("cooking_preferences") or []

        # Treating dietary restrictions more like hard constraints by pushing those
        # feature weights strongly upward in the target vector.
        for d in dietary:
            feat_name = f"is_{d.lower().replace('-', '_')}"
            if feat_name in user_profile:
                user_profile[feat_name] = 5.0

        # Treating cooking preferences as softer signals than dietary restrictions.
        # These adjustments nudge the profile without dominating it as strongly.
        for c in cooking:
            feat_name = f"is_{c.lower()}"
            if feat_name in user_profile:
                user_profile[feat_name] = 1.5
            elif c == "Fast":
                user_profile['is_fast'] = 1.5
            elif c == "Slow":
                user_profile['is_slow'] = 1.5
            elif c == "Easy":
                # Pushing difficulty toward the normalized low end.
                user_profile['difficulty_num'] = 0.0
            elif c == "Hard":
                # Pushing difficulty toward the normalized high end.
                user_profile['difficulty_num'] = 1.0

    # Excluding recipes the user already saved or cooked.
    # Recommendations should focus on unseen candidates, not old matches.
    target_df = df[~user_mask].copy()

    if target_df.empty:
        return []

    # Fitting the KNN model on the remaining candidate recipes.
    X = target_df[features].values
    k_neighbors = min(limit * 2, len(target_df))
    knn_model = NearestNeighbors(n_neighbors=k_neighbors, algorithm='auto', metric='euclidean')
    knn_model.fit(X)

    # Finding the recipes closest to the user's target profile in feature space.
    distances, indices = knn_model.kneighbors([user_profile.values])

    # Converting the nearest-neighbor results back into normal recipe records.
    recommended = target_df.iloc[indices[0]]
    recipes = recommended.to_dict(orient="records")

    # Removing duplicates and trimming the final list to the requested limit.
    return deduplicate_recipes(recipes)[:limit]
