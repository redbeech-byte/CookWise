import streamlit as st
import json
import re
import requests
import plotly.graph_objects as go
import datetime
from helpers.db import get_recipe_by_id, get_ingredients_for_recipe
from helpers.supabase_client import supabase, get_current_user, get_vault_secrets

# Defining the daily reference values, from WHO, used as the 100% target in the NutriRadar.
# These values give the chart a stable baseline, even though recipe nutrition is estimated.
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
    # Converting the ID to a string keeps Supabase lookups consistent.
    # Some parts of the app may pass recipe IDs as numbers, while cached nutrition rows use strings.
    recipe_id = str(recipe_id)
    
    # Checking the central nutrition cache before calling Gemini.
    # This avoids repeated API calls for recipes that were already estimated once.
    try:
        res = supabase.table("recipe_nutrition").select("*").eq("recipe_id", recipe_id).execute()
        if res.data:
            d = res.data[0]

            # Returning the database row in the same capitalized format used by the radar chart.
            # Supabase columns are lowercase, while the chart categories are title-cased.
            return {
                "Proteins": d["proteins"], 
                "Carbs": d["carbs"], 
                "Sugar": d["sugar"], 
                "Vitamins": d["vitamins"], 
                "Salt": d["salt"], 
                "Fats": d["fats"]
            }
    except Exception as e:
        # Cache lookup failure should not block the whole feature.
        # The function can still try to generate a fresh estimate below.
        print(f"Supabase fetch error: {e}")

    # Loading recipe details only when no cached nutrition exists.
    # Without a recipe title and ingredients, Gemini has no context for the estimate.
    recipe = get_recipe_by_id(recipe_id)
    if not recipe:
        return None
        
    ingredients = get_ingredients_for_recipe(recipe_id)

    # Building a readable ingredient string for the Gemini prompt.
    # The original ingredient text is used because it usually contains amounts and preparation clues.
    ingredients_text = ", ".join([ing.get("original_string", "") for ing in ingredients])
    title = recipe.get("recipe_title", "")
    
    # Asking Gemini for percentages of daily reference values instead of raw grams.
    # This keeps the output directly compatible with the radar chart scale.
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
    
    # Loading Gemini keys from Supabase Vault first.
    # The secondary key is a fallback for quota/rate-limit problems on the primary key.
    vault = get_vault_secrets()
    api_key_primary = vault.get("GEMINI_API_KEY")
    api_key_secondary = vault.get("GEMINI_API_KEY_SECONDARY")
    
    if not api_key_primary:
        # Falling back to local Streamlit secrets keeps local development possible.
        # This matters when Vault is empty, unavailable, or not configured for a new environment.
        api_key_primary = st.secrets.get("GEMINI_API_KEY")
        api_key_secondary = st.secrets.get("GEMINI_API_KEY_SECONDARY")

    if not api_key_primary:
        # Returning zeros keeps the radar chart renderable even when nutrition estimation cannot run.
        # This is preferable to crashing the recipe page because one external API key is missing.
        st.error("Gemini API Key missing in Vault and local secrets.")
        return {"Proteins": 0, "Carbs": 0, "Sugar": 0, "Vitamins": 0, "Salt": 0, "Fats": 0}

    success, result_text, error_msg = call_gemini_nutrition_api(prompt, api_key_primary)
    if not success and api_key_secondary:
        # Retrying with a secondary key handles temporary quota failures without changing the UI flow.
        success, result_text, error_msg = call_gemini_nutrition_api(prompt, api_key_secondary)

    if not success:
        # Returning zeros signals unavailable nutrition data while preserving the expected data shape.
        return {"Proteins": 0, "Carbs": 0, "Sugar": 0, "Vitamins": 0, "Salt": 0, "Fats": 0}

    # Extracting the JSON object defensively in case the model adds extra text despite the prompt.
    json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
    if json_match:
        result_text = json_match.group(0)

    try:
        data = json.loads(result_text)
        
        # Saving generated nutrition back to Supabase creates a shared cache.
        # Future users can reuse the estimate instead of spending another Gemini request.
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
        # Invalid JSON or failed caching should not break the page.
        # The zero fallback keeps downstream chart code simple and predictable.
        print(f"Error processing nutrition: {e}")
        return {"Proteins": 0, "Carbs": 0, "Sugar": 0, "Vitamins": 0, "Salt": 0, "Fats": 0}

def call_gemini_nutrition_api(prompt, api_key):
    try:
        # Calling Gemini Flash Lite because nutrition estimation is text-only and should be relatively fast.
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": { "response_mime_type": "application/json" }
        }

        # A timeout prevents the Streamlit page from hanging indefinitely if the API stalls.
        response = requests.post(url, json=payload, timeout=20)
        response.raise_for_status()
        res_json = response.json()

        # Gemini responses are nested, so this extracts the actual generated text from the first candidate.
        text = res_json.get('candidates', [])[0].get('content', {}).get('parts', [])[0].get('text', '')
        return True, text, ""
    except Exception as e:
        # Returning a success flag keeps API error handling in the caller explicit and easy to follow.
        return False, "", str(e)

@st.cache_data(ttl=60) # Short cache for today's stats
def get_todays_nutrition(user_id):
    """
    Calculates the ACTUAL sum of nutrition for meals cooked strictly TODAY.
    """
    # Starting at local midnight makes this a calendar-day view, not a rolling 24-hour view.
    # This distinction matters because the radar labels describe today's intake.
    today_start = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    res = supabase.table("cooked_recipes").select("recipe_id").eq("user_id", user_id).gte("cooked_at", today_start).execute()
    
    cooked_recipes = res.data or []
    totals = {"Proteins": 0, "Carbs": 0, "Sugar": 0, "Vitamins": 0, "Salt": 0, "Fats": 0}
    
    # Adding each cooked recipe's nutrition to today's total.
    # Missing nutrition is skipped so one failed estimate does not invalidate the whole day.
    for item in cooked_recipes:
        nut = get_recipe_nutrition(item["recipe_id"])
        if nut:
            for k in totals:
                totals[k] += nut.get(k, 0)
                
    return {"count": len(cooked_recipes), "totals": totals}

@st.cache_data(ttl=300)
def get_past_7_days_nutrition(user_id):
    """
    Calculates a 'Representative Daily Quality' based on tracked meals.
    Logic: (Total Nut / Total Meals) * Expected Meals Per Day
    """
    # Defaulting to three expected meals if the profile is unavailable.
    # This value controls how a per-meal average is scaled into a typical full day.
    expected_meals = 3
    try:
        from helpers.supabase_client import get_profile
        profile = get_profile()
        if profile:
            # Falling back to 3 also handles older profile rows where the value may be None.
            expected_meals = profile.get("expected_meals_per_day") or 3
    except Exception:
        # Profile loading should not prevent the chart from rendering.
        # The default expected meal count gives a reasonable fallback.
        pass

    # Fetching recent cooked recipes creates the historical comparison layer for the home radar.
    seven_days_ago = (datetime.datetime.now() - datetime.timedelta(days=7)).isoformat()
    res = supabase.table("cooked_recipes").select("recipe_id").eq("user_id", user_id).gte("cooked_at", seven_days_ago).execute()
    
    cooked_recipes = res.data or []
    count = len(cooked_recipes)
    
    if count == 0:
        # Returning the same data shape as the non-empty case keeps chart code simple.
        return {"count": 0, "totals": {"Proteins": 0, "Carbs": 0, "Sugar": 0, "Vitamins": 0, "Salt": 0, "Fats": 0}}

    totals = {"Proteins": 0, "Carbs": 0, "Sugar": 0, "Vitamins": 0, "Salt": 0, "Fats": 0}
    recipe_ids = [str(item["recipe_id"]) for item in cooked_recipes]
    
    # Fetching cached nutrition in one Supabase query avoids an N+1 pattern.
    # This is important because Streamlit reruns can otherwise repeat many slow remote calls.
    try:
        nut_res = supabase.table("recipe_nutrition").select("*").in_("recipe_id", recipe_ids).execute()
        nut_map = {str(item["recipe_id"]): item for item in (nut_res.data or [])}
    except Exception as e:
        print(f"Supabase batch fetch error: {e}")
        nut_map = {}
        
    for r_id in recipe_ids:
        if r_id in nut_map:
            # Cached rows use lowercase database column names, so each value is mapped manually.
            d = nut_map[r_id]
            totals["Proteins"] += d.get("proteins", 0)
            totals["Carbs"] += d.get("carbs", 0)
            totals["Sugar"] += d.get("sugar", 0)
            totals["Vitamins"] += d.get("vitamins", 0)
            totals["Salt"] += d.get("salt", 0)
            totals["Fats"] += d.get("fats", 0)
        else:
            # If one recipe is missing from the cache, generate it on demand and include it.
            # This gradually fills the central nutrition table as users interact with recipes.
            nut = get_recipe_nutrition(r_id)
            if nut:
                for k in totals:
                    totals[k] += nut.get(k, 0)
                
    # Scaling average meal quality to the user's expected number of meals creates a "typical day" estimate.
    # This is different from today's actual intake, so labels/comments must keep the concepts separate.
    daily_quality = {k: (v / float(count)) * expected_meals for k, v in totals.items()}
    
    return {"count": count, "expected_meals": expected_meals, "totals": daily_quality}

def draw_nutrition_radar(today_stats, average_stats=None, projected_recipe_nut=None):
    """
    Advanced NutriRadar with context-aware layers.
    - today_stats: Actual intake today (Red Area)
    - average_stats: Historical quality (Blue Dashed Line)
    - projected_recipe_nut: Potential impact (Green Line)
    """
    # The radar has six nutrition categories.
    # The first category is repeated at the end so Plotly closes the polygon shape.
    categories = ['Proteins', 'Carbs', 'Sugar', 'Vitamins', 'Salt', 'Fats']
    cats_loop = categories + [categories[0]]
    
    def to_list(d):
        # Converting dictionaries into ordered lists keeps every trace aligned to the same axes.
        # Missing values fall back to 0 so partial nutrition data still renders.
        return [d.get(c, 0) for c in categories] + [d.get(categories[0], 0)]
        
    fig = go.Figure()
    
    # Drawing the 100% daily target reference line.
    # There are 7 values because the first category is repeated to close the radar loop.
    target_vals = [100] * 7
    fig.add_trace(go.Scatterpolar(
        r=target_vals, theta=cats_loop, fill='none', name='Daily Target (100%)',
        line=dict(color='rgba(150,150,150,0.5)', dash='dot', width=1)
    ))
    
    # Adding historical average only when a caller provides it.
    # The home page uses this to compare today's intake against a typical recent day.
    if average_stats:
        avg_vals = to_list(average_stats)
        fig.add_trace(go.Scatterpolar(
            r=avg_vals, theta=cats_loop, fill='none', name='Typical Daily Quality',
            line=dict(color='rgba(0,0,255,0.6)', dash='dash', width=2)
        ))

    # Drawing today's actual tracked intake as the main filled area.
    # This should stay conceptually separate from the historical average layer.
    today_vals = to_list(today_stats)
    fig.add_trace(go.Scatterpolar(
        r=today_vals, theta=cats_loop, fill='toself', name="Today's Intake",
        line=dict(color='red', width=2), fillcolor='rgba(255,0,0,0.2)'
    ))
    
    # Adding a projection only on pages that pass in a candidate recipe's nutrition.
    # This shows how today's radar would change if the user cooked this recipe next.
    if projected_recipe_nut:
        proj_vals = []
        for i, c in enumerate(categories):
            proj_vals.append(today_vals[i] + projected_recipe_nut.get(c, 0))
        proj_vals.append(proj_vals[0])
        
        fig.add_trace(go.Scatterpolar(
            r=proj_vals, theta=cats_loop, fill='none', name='Today + This Meal',
            line=dict(color='green', dash='solid', width=3)
        ))
        
    # Expanding the radial axis dynamically prevents high values from being clipped.
    # The minimum range of 120 keeps the 100% target line visible with some breathing room.
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
