import streamlit as st
import json
import re
import requests
import plotly.graph_objects as go
import datetime
from helpers.db import get_recipe_by_id, get_ingredients_for_recipe
from helpers.supabase_client import supabase, get_current_user

# Primary and Secondary API Keys from st.secrets
GEMINI_API_KEY_PRIMARY = st.secrets["GEMINI_API_KEY"]
GEMINI_API_KEY_SECONDARY = st.secrets.get("GEMINI_API_KEY_SECONDARY")

# Standardized WHO Reference Values for an average adult (2000 kcal)
WHO_REFERENCES = {
    "Proteins": "50g",
    "Carbs": "275g",
    "Sugar": "50g",
    "Vitamins": "Daily RDA Mix",
    "Salt": "5g",
    "Fats": "78g"
}

def get_recipe_nutrition(recipe_id):
    """
    Retrieves or generates standardized nutritional data for a recipe.
    Data is stored on Supabase for cross-user consistency.
    """
    recipe_id = str(recipe_id)
    
    # 1. Try to fetch from Supabase (Central Cache)
    try:
        res = supabase.table("recipe_nutrition").select("*").eq("recipe_id", recipe_id).execute()
        if res.data:
            d = res.data[0]
            return {
                "Proteins": d["proteins"], 
                "Carbs": d["carbs"], 
                "Sugar": d["sugar"], 
                "Vitamins": d["vitamins"], 
                "Salt": d["salt"], 
                "Fats": d["fats"]
            }
    except Exception as e:
        print(f"Supabase fetch error: {e}")

    # 2. Not found, generate using Gemini with the "Hardened Concept"
    recipe = get_recipe_by_id(recipe_id)
    if not recipe:
        return None
        
    ingredients = get_ingredients_for_recipe(recipe_id)
    ingredients_text = ", ".join([ing.get("original_string", "") for ing in ingredients])
    title = recipe.get("recipe_title", "")
    
    # NEW CONCEPT: Explicit anchor points and forced portion math
    prompt = f"""
    You are a clinical nutritionist using WHO standardized reference values.
    
    TASK: Estimate the nutritional impact of ONE TYPICAL SERVING of this recipe.
    RECIPE: "{title}"
    INGREDIENTS: {ingredients_text}
    
    REFERENCE DAILY VALUES (100%):
    - Protein: 50g
    - Carbs: 275g
    - Sugar: 50g (Added sugars)
    - Salt: 5g
    - Fats: 70g
    
    CALCULATION RULES:
    1. If the recipe serves multiple people, you MUST divide the totals to get ONE portion.
    2. Be realistic. A salad is rarely 50% protein. A pasta dish is likely 30-50% carbs.
    3. Return ONLY a JSON object.
    
    JSON FORMAT:
    {{
        "Proteins": <float, % of 50g>,
        "Carbs": <float, % of 275g>,
        "Sugar": <float, % of 50g>,
        "Vitamins": <float, overall % of daily micronutrients>,
        "Salt": <float, % of 5g>,
        "Fats": <float, % of 70g>
    }}
    """
    
    success, result_text, error_msg = call_gemini_nutrition_api(prompt, GEMINI_API_KEY_PRIMARY)
    if not success and GEMINI_API_KEY_SECONDARY:
        success, result_text, error_msg = call_gemini_nutrition_api(prompt, GEMINI_API_KEY_SECONDARY)

    if not success:
        return {"Proteins": 0, "Carbs": 0, "Sugar": 0, "Vitamins": 0, "Salt": 0, "Fats": 0}

    # Extract JSON
    json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
    if json_match:
        result_text = json_match.group(0)

    try:
        data = json.loads(result_text)
        
        # Save to Supabase for future use
        supabase.table("recipe_nutrition").upsert({
            "recipe_id": recipe_id,
            "proteins": data.get("Proteins", 0),
            "carbs": data.get("Carbs", 0),
            "sugar": data.get("Sugar", 0),
            "vitamins": data.get("Vitamins", 0),
            "salt": data.get("Salt", 0),
            "fats": data.get("Fats", 0)
        }).execute()
        
        return data
    except Exception as e:
        print(f"Error processing nutrition: {e}")
        return {"Proteins": 0, "Carbs": 0, "Sugar": 0, "Vitamins": 0, "Salt": 0, "Fats": 0}

def call_gemini_nutrition_api(prompt, api_key):
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": { "response_mime_type": "application/json" }
        }
        response = requests.post(url, json=payload, timeout=20)
        response.raise_for_status()
        res_json = response.json()
        text = res_json.get('candidates', [])[0].get('content', {}).get('parts', [])[0].get('text', '')
        return True, text, ""
    except Exception as e:
        return False, "", str(e)

@st.cache_data(ttl=300)
def get_past_7_days_nutrition(user_id):
    """
    Calculates a 'Representative Daily Quality' based on tracked meals.
    Logic: (Total Nut / Total Meals) * Expected Meals Per Day
    """
    # 1. Fetch user's expected meal count (default 3)
    expected_meals = 3
    try:
        from helpers.supabase_client import get_profile
        profile = get_profile()
        if profile:
            expected_meals = profile.get("expected_meals_per_day") or 3
    except Exception:
        pass

    # 2. Fetch history
    seven_days_ago = (datetime.datetime.now() - datetime.timedelta(days=7)).isoformat()
    res = supabase.table("cooked_recipes").select("recipe_id").eq("user_id", user_id).gte("cooked_at", seven_days_ago).execute()
    
    cooked_recipes = res.data or []
    count = len(cooked_recipes)
    
    if count == 0:
        return {"count": 0, "totals": {"Proteins": 0, "Carbs": 0, "Sugar": 0, "Vitamins": 0, "Salt": 0, "Fats": 0}}

    # 3. Sum everything
    totals = {"Proteins": 0, "Carbs": 0, "Sugar": 0, "Vitamins": 0, "Salt": 0, "Fats": 0}
    for item in cooked_recipes:
        nut = get_recipe_nutrition(item["recipe_id"])
        if nut:
            for k in totals:
                totals[k] += nut.get(k, 0)
                
    # 4. Calculate quality (average per meal scaled to a full day)
    # This answer: "If I ate like this all day (N times), here is where I'd land."
    daily_quality = {k: (v / float(count)) * expected_meals for k, v in totals.items()}
    
    return {"count": count, "expected_meals": expected_meals, "totals": daily_quality}

def draw_nutrition_radar(daily_avg, current_recipe_nut=None):
    """
    Visualizes the Representative Quality vs. WHO Target.
    """
    categories = ['Proteins', 'Carbs', 'Sugar', 'Vitamins', 'Salt', 'Fats']
    cats_loop = categories + [categories[0]]
    
    def to_list(d):
        return [d.get(c, 0) for c in categories] + [d.get(categories[0], 0)]
        
    actual_vals = to_list(daily_avg)
    target_vals = [100] * 7
    
    fig = go.Figure()
    
    # Target Line
    fig.add_trace(go.Scatterpolar(
        r=target_vals, theta=cats_loop, fill='none', name='Daily Target (100%)',
        line=dict(color='rgba(0,0,255,0.5)', dash='dash', width=2)
    ))
    
    # Current Quality
    fig.add_trace(go.Scatterpolar(
        r=actual_vals, theta=cats_loop, fill='toself', name='Typical Daily Quality',
        line=dict(color='red', width=2), fillcolor='rgba(255,0,0,0.2)'
    ))
    
    # Projected Quality (New Average)
    if current_recipe_nut:
        # Get count/expected from session or fresh (simplifying for visual impact)
        # We calculate the NEW average quality if this meal replaces the 'worst' or is added to a set.
        # Most intuitive: show how THIS SPECIFIC meal compares to the average.
        proj_vals = []
        for c in categories:
            # Shift the average towards this new meal's quality
            # This shows the potential 'pull' of this recipe on your stats.
            recipe_val = current_recipe_nut.get(c, 0)
            # If expected_meals = 3, one meal's quality is recipe_val * 3
            recipe_quality = recipe_val * 3 
            proj_vals.append(recipe_quality)
        proj_vals.append(proj_vals[0])
        
        fig.add_trace(go.Scatterpolar(
            r=proj_vals, theta=cats_loop, fill='none', name='Quality of This Recipe',
            line=dict(color='green', dash='dot', width=2)
        ))
        
    max_val = max(actual_vals)
    if current_recipe_nut:
        max_val = max(max_val, max(proj_vals))

    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, max(120, max_val * 1.2)])),
        showlegend=True, margin=dict(l=40, r=40, t=40, b=40),
        dragmode=False, hovermode=False
    )
    return fig
