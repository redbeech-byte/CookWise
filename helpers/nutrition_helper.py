import streamlit as st
import json
import re
import requests
import plotly.graph_objects as go
import datetime
from helpers.db import get_recipe_by_id, get_ingredients_for_recipe
from helpers.supabase_client import supabase, get_current_user, get_vault_secrets

# Standardized WHO reference values for an average adult diet.
# These labels are used by the nutrition radar chart and by the Gemini prompt.
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
    Return nutrition percentages for one typical serving of a recipe.

    The function first checks the central Supabase cache. If the recipe has not
    been analyzed yet, it asks Gemini to estimate nutrition values, stores the
    result in Supabase, and returns the generated data.

    Args:
        recipe_id: The ID of the recipe to look up.

    Returns:
        A dictionary containing nutrition percentages for Proteins, Carbs,
        Sugar, Vitamins, Salt, and Fats. Returns None if the recipe does not
        exist, or zero-values if nutrition generation fails.
    """
    recipe_id = str(recipe_id)
    
    # Check Supabase first so recipes that were already analyzed do not need
    # another Gemini API call.
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

    # If the recipe is not cached yet, load its details and let Gemini estimate
    # the nutrition data.
    recipe = get_recipe_by_id(recipe_id)
    if not recipe:
        return None
        
    ingredients = get_ingredients_for_recipe(recipe_id)
    ingredients_text = ", ".join([ing.get("original_string", "") for ing in ingredients])
    title = recipe.get("recipe_title", "")
    
    # The prompt gives Gemini strict daily reference values and forces it to
    # estimate nutrition for one serving, not for the whole recipe.
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
    
    # Load Gemini API keys from the Supabase vault first.
    # The secondary key is used as a backup if the primary call fails.
    vault = get_vault_secrets()
    api_key_primary = vault.get("GEMINI_API_KEY")
    api_key_secondary = vault.get("GEMINI_API_KEY_SECONDARY")
    
    if not api_key_primary:
        # Fallback to Streamlit local secrets if the vault is empty or fails.
        api_key_primary = st.secrets.get("GEMINI_API_KEY")
        api_key_secondary = st.secrets.get("GEMINI_API_KEY_SECONDARY")

    if not api_key_primary:
        st.error("Gemini API Key missing in Vault and local secrets.")
        return {"Proteins": 0, "Carbs": 0, "Sugar": 0, "Vitamins": 0, "Salt": 0, "Fats": 0}

    success, result_text, error_msg = call_gemini_nutrition_api(prompt, api_key_primary)
    if not success and api_key_secondary:
        # Retry with the backup key before giving up.
        success, result_text, error_msg = call_gemini_nutrition_api(prompt, api_key_secondary)

    if not success:
        return {"Proteins": 0, "Carbs": 0, "Sugar": 0, "Vitamins": 0, "Salt": 0, "Fats": 0}

    # Gemini is instructed to return JSON, but this makes the parser safer in
    # case the response includes extra text before or after the JSON object.
    json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
    if json_match:
        result_text = json_match.group(0)

    try:
        data = json.loads(result_text)
        
        # Save the generated nutrition data so future users/requests can reuse
        # it without calling Gemini again.
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
    """
    Send a nutrition prompt to Gemini and return the raw JSON response text.

    Args:
        prompt: The full instruction prompt sent to Gemini.
        api_key: Gemini API key used for this request.

    Returns:
        A tuple of (success, response_text, error_message).
    """
    try:
        # Gemini endpoint used for lightweight nutrition estimation.
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": { "response_mime_type": "application/json" }
        }
        # Timeout prevents the Streamlit app from hanging too long if Gemini is slow.
        response = requests.post(url, json=payload, timeout=20)
        response.raise_for_status()
        res_json = response.json()
        # Gemini responses are nested, so this extracts the generated text from
        # the first candidate safely using default fallbacks.
        text = res_json.get('candidates', [])[0].get('content', {}).get('parts', [])[0].get('text', '')
        return True, text, ""
    except Exception as e:
        return False, "", str(e)

@st.cache_data(ttl=60) # Short cache for today's stats
def get_todays_nutrition(user_id):
    """
    Calculate the total nutrition percentages for meals cooked today.

    Args:
        user_id: The current user's ID.

    Returns:
        A dictionary containing the number of cooked recipes today and the
        summed nutrition totals for those recipes.
    """
    # Start counting from midnight today so only today's cooked meals are included.
    today_start = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    res = supabase.table("cooked_recipes").select("recipe_id").eq("user_id", user_id).gte("cooked_at", today_start).execute()
    
    cooked_recipes = res.data or []
    totals = {"Proteins": 0, "Carbs": 0, "Sugar": 0, "Vitamins": 0, "Salt": 0, "Fats": 0}
    
    # Add each cooked recipe's cached/generated nutrition values into today's totals.
    for item in cooked_recipes:
        nut = get_recipe_nutrition(item["recipe_id"])
        if nut:
            for k in totals:
                totals[k] += nut.get(k, 0)
                
    return {"count": len(cooked_recipes), "totals": totals}

@st.cache_data(ttl=300)
def get_past_7_days_nutrition(user_id):
    """
    Calculate a representative daily nutrition score from the last 7 days.

    Instead of simply summing the last week, this calculates an average meal
    quality and scales it by the user's expected meals per day.

    Formula:
        (Total nutrition / Total meals tracked) * Expected meals per day

    Args:
        user_id: The current user's ID.

    Returns:
        A dictionary containing the number of meals, expected meals per day,
        and scaled nutrition totals.
    """
    # Use the user's expected meal count when available; otherwise assume a
    # standard 3 meals per day.
    expected_meals = 3
    try:
        from helpers.supabase_client import get_profile
        profile = get_profile()
        if profile:
            expected_meals = profile.get("expected_meals_per_day") or 3
    except Exception:
        pass

    # Look at the user's cooked meals from the past 7 days.
    seven_days_ago = (datetime.datetime.now() - datetime.timedelta(days=7)).isoformat()
    res = supabase.table("cooked_recipes").select("recipe_id").eq("user_id", user_id).gte("cooked_at", seven_days_ago).execute()
    
    cooked_recipes = res.data or []
    count = len(cooked_recipes)
    
    if count == 0:
        return {"count": 0, "totals": {"Proteins": 0, "Carbs": 0, "Sugar": 0, "Vitamins": 0, "Salt": 0, "Fats": 0}}

    # Sum the nutrition values for each cooked recipe.
    totals = {"Proteins": 0, "Carbs": 0, "Sugar": 0, "Vitamins": 0, "Salt": 0, "Fats": 0}
    recipe_ids = [str(item["recipe_id"]) for item in cooked_recipes]
    
    # Fetch all cached nutrition rows in one query to avoid making one Supabase
    # request per recipe.
    try:
        nut_res = supabase.table("recipe_nutrition").select("*").in_("recipe_id", recipe_ids).execute()
        nut_map = {str(item["recipe_id"]): item for item in (nut_res.data or [])}
    except Exception as e:
        print(f"Supabase batch fetch error: {e}")
        nut_map = {}
        
    for r_id in recipe_ids:
        if r_id in nut_map:
            # Use cached Supabase values when they already exist.
            d = nut_map[r_id]
            totals["Proteins"] += d.get("proteins", 0)
            totals["Carbs"] += d.get("carbs", 0)
            totals["Sugar"] += d.get("sugar", 0)
            totals["Vitamins"] += d.get("vitamins", 0)
            totals["Salt"] += d.get("salt", 0)
            totals["Fats"] += d.get("fats", 0)
        else:
            # If a recipe is missing from the cache, generate and save it now.
            nut = get_recipe_nutrition(r_id)
            if nut:
                for k in totals:
                    totals[k] += nut.get(k, 0)
                
    # Convert the average tracked meal into a representative full-day value
    # based on the user's expected number of meals.
    daily_quality = {k: (v / float(count)) * expected_meals for k, v in totals.items()}
    
    return {"count": count, "expected_meals": expected_meals, "totals": daily_quality}

def draw_nutrition_radar(today_stats, average_stats=None, projected_recipe_nut=None):
    """
    Build the Plotly radar chart used to visualize nutrition progress.

    Chart layers:
        - Daily target: 100% reference line.
        - Today's intake: Actual nutrition consumed today.
        - Historical average: Optional representative daily nutrition quality.
        - Projected intake: Optional total if the user cooks the selected recipe.

    Args:
        today_stats: Actual nutrition totals for today.
        average_stats: Optional historical average/quality values.
        projected_recipe_nut: Optional nutrition values for a possible next meal.

    Returns:
        A Plotly Figure object containing the nutrition radar chart.
    """
    categories = ['Proteins', 'Carbs', 'Sugar', 'Vitamins', 'Salt', 'Fats']
    # Repeat the first category at the end so the radar chart closes into a loop.
    cats_loop = categories + [categories[0]]
    
    def to_list(d):
        """Convert a nutrition dictionary into a closed radar-chart value list."""
        return [d.get(c, 0) for c in categories] + [d.get(categories[0], 0)]
        
    fig = go.Figure()
    
    # The target line shows the 100% daily reference for every category.
    target_vals = [100] * 7
    fig.add_trace(go.Scatterpolar(
        r=target_vals, theta=cats_loop, fill='none', name='Daily Target (100%)',
        line=dict(color='rgba(150,150,150,0.5)', dash='dot', width=1)
    ))
    
    # Show the historical average when this chart is used on the home page.
    if average_stats:
        avg_vals = to_list(average_stats)
        fig.add_trace(go.Scatterpolar(
            r=avg_vals, theta=cats_loop, fill='none', name='Typical Daily Quality',
            line=dict(color='rgba(0,0,255,0.6)', dash='dash', width=2)
        ))

    # Today's actual progress is always shown as the main filled area.
    today_vals = to_list(today_stats)
    fig.add_trace(go.Scatterpolar(
        r=today_vals, theta=cats_loop, fill='toself', name="Today's Intake",
        line=dict(color='red', width=2), fillcolor='rgba(255,0,0,0.2)'
    ))
    
    # On recipe detail pages, this previews how the selected recipe would change
    # today's total nutrition.
    if projected_recipe_nut:
        proj_vals = []
        for i, c in enumerate(categories):
            proj_vals.append(today_vals[i] + projected_recipe_nut.get(c, 0))
        proj_vals.append(proj_vals[0])
        
        fig.add_trace(go.Scatterpolar(
            r=proj_vals, theta=cats_loop, fill='none', name='Today + This Meal',
            line=dict(color='green', dash='solid', width=3)
        ))
        
    # Calculate the axis range dynamically so high values are still visible.
    all_vals = today_vals + target_vals
    if average_stats: all_vals += to_list(average_stats)
    if projected_recipe_nut: all_vals += proj_vals
    
    max_val = max(all_vals)
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, max(120, max_val * 1.1)])),
        showlegend=True, margin=dict(l=60, r=60, t=40, b=40),
        dragmode=False, hovermode=False
    )
    return fig
