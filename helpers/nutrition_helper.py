import streamlit as st
import json
import re
import requests
import plotly.graph_objects as go
import datetime
from helpers.db import get_recipe_by_id, get_ingredients_for_recipe
from helpers.supabase_client import supabase, get_current_user, get_vault_secrets

# Standardized WHO-style reference values for an average adult diet.
# The chart and Gemini prompt use the same categories so the estimated values
# and the visual labels stay aligned.
WHO_REFERENCES = {
    "Proteins": "50g",
    "Carbs": "275g",
    "Sugar": "50g",
    "Vitamins": "Daily RDA Mix",
    "Salt": "5g",
    "Fats": "78g"
}

def get_recipe_nutrition(recipe_id):
    # Returning nutrition percentages for one typical serving of a recipe.
    # These values are estimates, not measured lab data.
    # Supabase is checked first because repeated Gemini calls would be slower,
    # more costly, and could give slightly different answers for the same recipe.
    # If no cached row exists, Gemini estimates the values and the result is saved.
    recipe_id = str(recipe_id)
    
    # Checking Supabase first keeps the same recipe consistent across users and
    # avoids asking Gemini to re-estimate nutrition that was already generated.
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

    # If the recipe is not cached yet, the recipe title and ingredient strings
    # become the context Gemini uses for the estimate.
    recipe = get_recipe_by_id(recipe_id)
    if not recipe:
        return None
        
    ingredients = get_ingredients_for_recipe(recipe_id)
    # Using the original ingredient strings preserves quantities and wording from
    # the recipe database, which gives Gemini more useful context than names alone.
    ingredients_text = ", ".join([ing.get("original_string", "") for ing in ingredients])
    title = recipe.get("recipe_title", "")
    
    # The prompt anchors Gemini to daily reference values and asks for one
    # typical serving. This avoids the earlier conceptual problem where recipe
    # totals and daily nutrition targets could be mixed too loosely.
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
    
    # Loading Gemini keys from Supabase Vault keeps API credentials out of the
    # main code path while still letting the app run for authenticated users.
    # The secondary key gives the app a fallback if the primary key is rate-limited
    # or temporarily unavailable.
    vault = get_vault_secrets()
    api_key_primary = vault.get("GEMINI_API_KEY")
    api_key_secondary = vault.get("GEMINI_API_KEY_SECONDARY")
    
    if not api_key_primary:
        # Falling back to Streamlit secrets supports local development, where Vault
        # may not be available yet.
        api_key_primary = st.secrets.get("GEMINI_API_KEY")
        api_key_secondary = st.secrets.get("GEMINI_API_KEY_SECONDARY")

    if not api_key_primary:
        # Returning zeros keeps the NutriRadar from crashing when credentials are missing,
        # but it also means the displayed nutrition is only a safe fallback.
        st.error("Gemini API Key missing in Vault and local secrets.")
        return {"Proteins": 0, "Carbs": 0, "Sugar": 0, "Vitamins": 0, "Salt": 0, "Fats": 0}

    success, result_text, error_msg = call_gemini_nutrition_api(prompt, api_key_primary)
    if not success and api_key_secondary:
        # Retrying with the backup key handles temporary key-specific failures without
        # changing the rest of the nutrition flow.
        success, result_text, error_msg = call_gemini_nutrition_api(prompt, api_key_secondary)

    if not success:
        # Failed estimates return zeros so downstream totals can still be calculated
        # with the expected keys instead of breaking on missing nutrition data.
        return {"Proteins": 0, "Carbs": 0, "Sugar": 0, "Vitamins": 0, "Salt": 0, "Fats": 0}

    # Gemini is instructed to return JSON, but extracting the object makes parsing
    # safer if the model adds extra text around the response.
    json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
    if json_match:
        result_text = json_match.group(0)

    try:
        data = json.loads(result_text)
        
        # Saving the generated values turns this estimate into the shared cached
        # version for future requests.
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
        # JSON parsing or Supabase saving can fail if Gemini returns malformed data.
        # Returning the same zero-shape keeps the chart code simple and predictable.
        print(f"Error processing nutrition: {e}")
        return {"Proteins": 0, "Carbs": 0, "Sugar": 0, "Vitamins": 0, "Salt": 0, "Fats": 0}

def call_gemini_nutrition_api(prompt, api_key):
    # Sending the nutrition prompt to Gemini and returning the raw response text.
    # Keeping the HTTP request separate from the nutrition logic above makes key
    # retrying and JSON post-processing easier to follow.
    try:
        # Gemini endpoint used for lightweight nutrition estimation.
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": { "response_mime_type": "application/json" }
        }
        # The timeout prevents the Streamlit app from hanging too long if Gemini is slow
        # or the network request gets stuck.
        response = requests.post(url, json=payload, timeout=20)
        response.raise_for_status()
        res_json = response.json()
        # Gemini responses are nested. This extracts the text from the first candidate,
        # which is where the model's JSON response is expected to appear.
        text = res_json.get('candidates', [])[0].get('content', {}).get('parts', [])[0].get('text', '')
        return True, text, ""
    except Exception as e:
        # Returning a success flag keeps API error handling in the caller explicit and easy to follow.
        return False, "", str(e)

@st.cache_data(ttl=60) # Short cache for today's stats
def get_todays_nutrition(user_id):
    # Calculating the total nutrition percentages for meals cooked today.
    # The current calendar day starts at midnight, so the red NutriRadar layer
    # represents today's tracked intake rather than a weekly average or rolling
    # 24-hour window.
    # Starting from midnight keeps the chart on a daily scale, matching the daily
    # target line shown in the radar chart.
    today_start = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    res = supabase.table("cooked_recipes").select("recipe_id").eq("user_id", user_id).gte("cooked_at", today_start).execute()
    
    cooked_recipes = res.data or []
    totals = {"Proteins": 0, "Carbs": 0, "Sugar": 0, "Vitamins": 0, "Salt": 0, "Fats": 0}
    
    # Adding each cooked recipe's cached or generated nutrition values creates
    # the actual tracked intake for today.
    for item in cooked_recipes:
        nut = get_recipe_nutrition(item["recipe_id"])
        if nut:
            for k in totals:
                totals[k] += nut.get(k, 0)
                
    return {"count": len(cooked_recipes), "totals": totals}

@st.cache_data(ttl=300)
def get_past_7_days_nutrition(user_id):
    # Calculating a representative daily nutrition score from the last 7 days.
    # This is not the same as today's actual intake. It uses recent cooked meals
    # to estimate what a typical full day looks like, then scales the average
    # tracked meal by the expected number of meals per day.
    # Formula: (Total nutrition / Total meals tracked) * Expected meals per day.
    # Using the profile value keeps the historical estimate personal. Falling
    # back to 3 meals avoids failing when the profile field is missing or None.
    expected_meals = 3
    try:
        from helpers.supabase_client import get_profile
        profile = get_profile()
        if profile:
            # Falling back to 3 also handles older profile rows where the value may be None.
            expected_meals = profile.get("expected_meals_per_day") or 3
    except Exception:
        # If the profile cannot be loaded, keep the default meal assumption so
        # the historical chart layer can still be calculated.
        pass

    # Looking at the past 7 days gives a recent history without mixing it into
    # today's actual intake calculation.
    seven_days_ago = (datetime.datetime.now() - datetime.timedelta(days=7)).isoformat()
    res = supabase.table("cooked_recipes").select("recipe_id").eq("user_id", user_id).gte("cooked_at", seven_days_ago).execute()
    
    cooked_recipes = res.data or []
    count = len(cooked_recipes)
    
    if count == 0:
        # Returning the same totals shape avoids special-case handling in the chart
        # when the user has not tracked any cooked meals yet.
        return {"count": 0, "totals": {"Proteins": 0, "Carbs": 0, "Sugar": 0, "Vitamins": 0, "Salt": 0, "Fats": 0}}

    # Summing starts from recipe ids in cooked history, then connects each id to
    # its nutrition row or generates one if needed.
    totals = {"Proteins": 0, "Carbs": 0, "Sugar": 0, "Vitamins": 0, "Salt": 0, "Fats": 0}
    recipe_ids = [str(item["recipe_id"]) for item in cooked_recipes]
    
    # Fetching cached nutrition rows in one query avoids an N+1 pattern, where
    # every cooked recipe would otherwise trigger its own Supabase request.
    try:
        nut_res = supabase.table("recipe_nutrition").select("*").in_("recipe_id", recipe_ids).execute()
        nut_map = {str(item["recipe_id"]): item for item in (nut_res.data or [])}
    except Exception as e:
        print(f"Supabase batch fetch error: {e}")
        nut_map = {}
        
    for r_id in recipe_ids:
        if r_id in nut_map:
            # Using cached values here keeps the 7-day calculation faster and
            # avoids unnecessary Gemini calls during page reruns.
            d = nut_map[r_id]
            totals["Proteins"] += d.get("proteins", 0)
            totals["Carbs"] += d.get("carbs", 0)
            totals["Sugar"] += d.get("sugar", 0)
            totals["Vitamins"] += d.get("vitamins", 0)
            totals["Salt"] += d.get("salt", 0)
            totals["Fats"] += d.get("fats", 0)
        else:
            # If a recipe is missing from the cache, generating it here fills the
            # gap and also saves the estimate for future calculations.
            nut = get_recipe_nutrition(r_id)
            if nut:
                for k in totals:
                    totals[k] += nut.get(k, 0)
                
    # Converting the average tracked meal into a representative full-day value
    # makes the blue layer comparable to a daily target, not a raw 7-day total.
    daily_quality = {k: (v / float(count)) * expected_meals for k, v in totals.items()}
    
    return {"count": count, "expected_meals": expected_meals, "totals": daily_quality}

def draw_nutrition_radar(today_stats, average_stats=None, projected_recipe_nut=None):
    # Building the Plotly radar chart used to visualize nutrition progress.
    # The radar combines different layers, so the time scale needs to stay clear:
    # today's intake is actual tracked intake for the day, the historical line is
    # a representative daily estimate, and the projection shows what today's total
    # would look like after one possible meal.
    categories = ['Proteins', 'Carbs', 'Sugar', 'Vitamins', 'Salt', 'Fats']
    # Repeating the first category at the end closes the radar polygon visually.
    cats_loop = categories + [categories[0]]
    
    def to_list(d):
        # Converting a nutrition dictionary into the closed value list Plotly expects.
        return [d.get(c, 0) for c in categories] + [d.get(categories[0], 0)]
        
    fig = go.Figure()
    
    # The target line shows the 100% daily reference for every category.
    # There are 7 values because the 6 nutrition categories need the first value
    # repeated at the end to close the radar shape.
    target_vals = [100] * 7
    fig.add_trace(go.Scatterpolar(
        r=target_vals, theta=cats_loop, fill='none', name='Daily Target (100%)',
        line=dict(color='rgba(150,150,150,0.5)', dash='dot', width=1)
    ))
    
    # Showing the historical average gives context for what the user's typical
    # tracked day looks like, separate from today's actual intake.
    if average_stats:
        avg_vals = to_list(average_stats)
        fig.add_trace(go.Scatterpolar(
            r=avg_vals, theta=cats_loop, fill='none', name='Typical Daily Quality',
            line=dict(color='rgba(0,0,255,0.6)', dash='dash', width=2)
        ))

    # Today's actual progress is always shown as the main filled area because it
    # is the user's current tracked intake against the daily target.
    today_vals = to_list(today_stats)
    fig.add_trace(go.Scatterpolar(
        r=today_vals, theta=cats_loop, fill='toself', name="Today's Intake",
        line=dict(color='red', width=2), fillcolor='rgba(255,0,0,0.2)'
    ))
    
    # On recipe detail pages, this previews how the selected recipe would change
    # today's total nutrition if the user cooked it.
    if projected_recipe_nut:
        proj_vals = []
        for i, c in enumerate(categories):
            proj_vals.append(today_vals[i] + projected_recipe_nut.get(c, 0))
        proj_vals.append(proj_vals[0])
        
        fig.add_trace(go.Scatterpolar(
            r=proj_vals, theta=cats_loop, fill='none', name='Today + This Meal',
            line=dict(color='green', dash='solid', width=3)
        ))
        
    # Calculating the axis range dynamically keeps high values visible instead
    # of cutting off categories that go above the 100% target.
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
