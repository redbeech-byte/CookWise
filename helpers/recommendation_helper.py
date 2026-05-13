import pandas as pd
import numpy as np
import streamlit as st
from sklearn.neighbors import NearestNeighbors
from sklearn.feature_extraction.text import TfidfVectorizer
from helpers.db import deduplicate_recipes
from helpers.supabase_client import get_saved_recipes, get_cooked_recipes, supabase


@st.cache_data(ttl=86400)
def load_base_features():
    # Loading recipe features used by the KNN recommendation model.
    # This includes normal recipe metadata plus ingredient text that gets converted
    # into TF-IDF features, so recommendations can consider both structure and flavor.
    res = supabase.table("recipes").select("""
        recipe_id, recipe_title, est_prep_time_min, est_cook_time_min, 
        difficulty, is_vegan, is_vegetarian, is_gluten_free, is_dairy_free, is_nut_free, is_halal, is_kosher,
        primary_taste, secondary_taste, cook_speed, num_ingredients, num_steps, main_ingredient,
        recipe_ingredients(ingredients(pure_ingredient_harsh))
    """).execute()

    df = pd.DataFrame(res.data or [])

    # Returning early if no recipe data is available.
    if df.empty:
        # Returning an empty feature list keeps the recommendation function from
        # trying to train a model when Supabase returns no recipe data.
        return df, []
        
    # Extracting ingredient names into one text string per recipe for TF-IDF.
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
        
    # Storing the joined ingredient text beside the recipe rows so the vectorizer
    # can turn ingredient wording into numeric similarity features.
    df['ingredient_text'] = ingredient_texts
        
    # Mapping categorical difficulty values to numbers so KNN can compare them.
    # Database stores lowercase 'easy', 'medium', 'hard'.
    df['difficulty_num'] = df['difficulty'].str.lower().map({'easy': 1, 'medium': 2, 'hard': 3}).fillna(1)
    # Total time combines preparation and cooking because both affect whether a
    # recipe feels quick or demanding to the user.
    df['total_time'] = df['est_prep_time_min'].fillna(0) + df['est_cook_time_min'].fillna(0)
    
    # Filling missing numeric values with the median avoids losing recipes just
    # because one recipe has incomplete metadata.
    df['num_ingredients'] = df['num_ingredients'].fillna(df['num_ingredients'].median())
    df['num_steps'] = df['num_steps'].fillna(df['num_steps'].median())
    
    # Creates a boolean mask based on user prefrences.
    tastes = ["Spicy", "Sweet", "Savory", "Umami"]
    for t in tastes:
        # Checking both primary and secondary taste against the lowercase tag.
        df[f'is_{t.lower()}'] = ((df['primary_taste'].str.lower() == t.lower()) | (df['secondary_taste'].str.lower() == t.lower())).astype(int)

    # Cook speed is also converted into flags because users may prefer quick or
    # slower recipes independently of total minutes.
    df['is_fast'] = (df['cook_speed'].str.lower() == 'fast').astype(int)
    df['is_slow'] = (df['cook_speed'].str.lower() == 'slow').astype(int)

    # Encoding main ingredients as boolean columns helps the model separate broad
    # recipe types like poultry, seafood, plant-based, or egg/dairy dishes.
    main_ings = ['poultry', 'red_meat', 'seafood', 'plant', 'egg_dairy']
    for ing in main_ings:
        df[f'main_{ing}'] = (df['main_ingredient'].str.lower() == ing).astype(int)

    # Defining the handcrafted numeric feature set used for similarity matching.
    base_features = ['total_time', 'difficulty_num', 'num_ingredients', 'num_steps',
                'is_vegan', 'is_vegetarian', 'is_gluten_free', 'is_dairy_free',
                'is_nut_free', 'is_halal', 'is_kosher', 'is_fast', 'is_slow'] + \
                [f'is_{t.lower()}' for t in tastes] + \
                [f'main_{ing}' for ing in main_ings]

    # Coercing all base features into numeric form so distance calculations stay stable.
    for f in base_features:
        # Coercing everything to numeric prevents strings or missing database values
        # from breaking the model input matrix.
        df[f] = pd.to_numeric(df[f], errors='coerce').fillna(0).astype(float)
        
    # Min-max normalization puts all base features on a similar 0-1 scale, so one
    # large numeric column does not dominate the distance calculation.
    for f in base_features:
        max_val = df[f].max()
        min_val = df[f].min()
        if max_val > min_val:
            df[f] = (df[f] - min_val) / (max_val - min_val)
    # TF-IDF allows for more dynamic flavor and ingredient-based recommendations
    # by identifiying patterns in the ingredient text.        
    tfidf = TfidfVectorizer(max_features=150, stop_words='english')
    tfidf_matrix = tfidf.fit_transform(df['ingredient_text'])
    
    # Storing TF-IDF values as columns makes them usable alongside the manually
    # engineered recipe features.
    tfidf_feature_names = [f"tfidf_{w}" for w in tfidf.get_feature_names_out()]
    tfidf_df = pd.DataFrame(tfidf_matrix.toarray(), columns=tfidf_feature_names)
    
    # Combining the TF-IDF dataframe with the main dataframe gives each recipe one
    # complete feature row for KNN.
    df = pd.concat([df, tfidf_df], axis=1)

    # Keeping a single feature list so the recommendation function knows exactly which columns to use.
    features = base_features + tfidf_feature_names

    # Storing recipe IDs as strings for safer comparison with Supabase-returned values.
    # This avoids mismatches where one source gives ints and another gives strings.
    df['recipe_id_str'] = df['recipe_id'].astype(str)
    return df, features


@st.cache_data(ttl=600)
def get_recommended_recipes(limit=10):
    # Calculating recommendations with K-Nearest Neighbors based on saved recipes,
    # cooked recipes, and explicit profile preferences.
    # The result is cached briefly because recommendations depend on user history
    # but do not need to be recalculated on every Streamlit rerun.
    from helpers.supabase_client import get_profile

    # Loading the user's saved and cooked history.
    # `or []` prevents iterable errors if a helper unexpectedly returns None.
    saved = get_saved_recipes() or []
    cooked = get_cooked_recipes() or []
    profile = get_profile()
    
    # Saved and cooked recipes together describe what the user has already shown
    # interest in, so both are used to build the recommendation profile.
    user_recipe_ids = set()
    for item in saved:
        user_recipe_ids.add(str(item.get("recipe_id")))
    for item in cooked:
        user_recipe_ids.add(str(item.get("recipe_id")))
        
    # Loading the normalized recipe feature table. This is cached separately because
    # the recipe dataset changes much less often than the user's interactions.
    loaded = load_base_features()
    if len(loaded) != 2 or (isinstance(loaded[0], pd.DataFrame) and loaded[0].empty):
        # If feature loading fails or returns no recipes, the app returns no recommendations
        # instead of trying to fit KNN on empty data.
        return []

    df, features = loaded
    
    # Building the base user profile from recipe history.
    user_mask = df['recipe_id_str'].isin(user_recipe_ids)
    user_df = df[user_mask]

    if user_df.empty:
        # If there is no history yet, starting with a neutral profile prevents the
        # model from inventing a preference from missing data.
        user_profile = pd.Series(0.0, index=features)
    else:
        # Averaging saved and cooked recipes creates a simple preference vector
        # representing the kind of recipes the user already likes or uses.
        user_profile = user_df[features].mean()

    # Adding explicit profile preferences on top of history makes the model respect
    # stated restrictions and tastes, not only past behavior.
    # Falling back to [] avoids the common bug where a missing/None profile field
    # would crash when the code tries to iterate over it.
    if profile:
        # Falling back to [] if the stored profile values are missing or None.
        # Prevents: 'NoneType' object is not iterable.
        dietary = profile.get("dietary_restrictions") or []
        cooking = profile.get("cooking_preferences") or []
        
        # Dietary restrictions are treated as strong signals in KNN space because
        # they are closer to requirements than casual preferences.
        for d in dietary:
            feat_name = f"is_{d.lower().replace('-', '_')}"
            if feat_name in user_profile:
                # Using a high weight pushes the nearest-neighbor search strongly
                # toward recipes that match this restriction.
                user_profile[feat_name] = 5.0 
        
        # Cooking preferences adjust taste, speed, and difficulty without making
        # them as strict as dietary restrictions.
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
                user_profile['difficulty_num'] = 1.0 # Push towards 1 (normalized Hard)

    # Calculating closest neighbors in the feature space.
    # Excluding recipes the user already saved or cooked keeps recommendations fresh.
    target_df = df[~user_mask].copy()

    if target_df.empty:
        # If the user has already interacted with every recipe in the dataset,
        # there is nothing new left to recommend.
        return []
        
    # Fitting the KNN model on candidate recipes only.
    X = target_df[features].values
    # Asking for more neighbors than the final limit gives deduplication some room
    # to remove repeated recipes without returning too few results.
    k_neighbors = min(limit * 2, len(target_df))
    knn_model = NearestNeighbors(n_neighbors=k_neighbors, algorithm='auto', metric='euclidean')
    knn_model.fit(X)
    
    # Finding the nearest recipes to the idealized user profile target vector.
    distances, indices = knn_model.kneighbors([user_profile.values])
    
    # Returning the closest recipes after deduplication so the UI receives a clean list.
    recommended = target_df.iloc[indices[0]]
    recipes = recommended.to_dict(orient="records")

    # Removing duplicates and trimming the final list to the requested limit.
    return deduplicate_recipes(recipes)[:limit]
