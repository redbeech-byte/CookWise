import streamlit as st
import sqlite3
import json
import re
import requests
import plotly.graph_objects as go
from helpers.db import DB_PATH, get_recipe_by_id, get_ingredients_for_recipe
from helpers.supabase_client import supabase, get_current_user
import datetime

# Primary and Secondary API Keys from st.secrets
GEMINI_API_KEY_PRIMARY = st.secrets["GEMINI_API_KEY"]
GEMINI_API_KEY_SECONDARY = st.secrets.get("GEMINI_API_KEY_SECONDARY")

def get_db_connection():
    return sqlite3.connect(DB_PATH)

def init_nutrition_table():
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS recipe_nutrition (
                recipe_id TEXT PRIMARY KEY,
                proteins REAL,
                carbs REAL,
                sugar REAL,
                vitamins REAL,
                salt REAL,
                fats REAL
            )
        """)

def get_recipe_nutrition(recipe_id):
    recipe_id = str(recipe_id)
    init_nutrition_table()
    with get_db_connection() as conn:
        res = conn.execute("SELECT proteins, carbs, sugar, vitamins, salt, fats FROM recipe_nutrition WHERE recipe_id = ?", (recipe_id,)).fetchone()
        if res:
            return {"Proteins": res[0], "Carbs": res[1], "Sugar": res[2], "Vitamins": res[3], "Salt": res[4], "Fats": res[5]}

    # Not found, generate using Gemini
    recipe = get_recipe_by_id(recipe_id)
    if not recipe:
        return None
    ingredients = get_ingredients_for_recipe(recipe_id)
    
    ingredients_text = ", ".join([ing.get("original_string", "") for ing in ingredients])
    title = recipe.get("recipe_title", "")
    
    prompt = f"""
    You are an expert nutritionist. Estimate the nutritional value for 1 portion of the following recipe:
    Title: {title}
    Ingredients: {ingredients_text}
    
    Return ONLY a valid JSON object with these exact keys, providing the estimated percentage of the Daily Value (% DV) based on WHO guidelines for an average adult:
    {{
        "Proteins": <float>,
        "Carbs": <float>,
        "Sugar": <float>,
        "Vitamins": <float>,
        "Salt": <float>,
        "Fats": <float>
    }}
    Do not include any other text, reasoning, or markdown.
    """
    
    success, result_text, error_msg = call_gemini_nutrition_api(prompt, GEMINI_API_KEY_PRIMARY)
    
    if not success and GEMINI_API_KEY_SECONDARY:
        success, result_text, error_msg = call_gemini_nutrition_api(prompt, GEMINI_API_KEY_SECONDARY)

    if not success:
        print(f"Error evaluating nutrition: {error_msg}")
        return {"Proteins": 0, "Carbs": 0, "Sugar": 0, "Vitamins": 0, "Salt": 0, "Fats": 0}

    json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
    if json_match:
        result_text = json_match.group(0)

    try:
        data = json.loads(result_text)
        
        with get_db_connection() as conn:
            conn.execute("""
                INSERT INTO recipe_nutrition (recipe_id, proteins, carbs, sugar, vitamins, salt, fats)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (str(recipe_id), data.get("Proteins", 0), data.get("Carbs", 0), data.get("Sugar", 0), data.get("Vitamins", 0), data.get("Salt", 0), data.get("Fats", 0)))
        
        return data
    except Exception as e:
        print(f"Error parsing nutrition JSON: {e}")
        return {"Proteins": 0, "Carbs": 0, "Sugar": 0, "Vitamins": 0, "Salt": 0, "Fats": 0}

def call_gemini_nutrition_api(prompt, api_key):
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "response_mime_type": "application/json"
            }
        }
        response = requests.post(url, json=payload, timeout=20)
        response.raise_for_status()
        
        res_json = response.json()
        candidates = res_json.get('candidates', [])
        if not candidates:
            return False, "", "No candidates"
            
        text = candidates[0].get('content', {}).get('parts', [])[0].get('text', '')
        return True, text, ""
    except Exception as e:
        return False, "", str(e)

@st.cache_data(ttl=300) # Cache weekly stats for 5 mins
def get_past_7_days_nutrition(user_id):
    seven_days_ago = (datetime.datetime.now() - datetime.timedelta(days=7)).isoformat()
    res = supabase.table("cooked_recipes").select("recipe_id").eq("user_id", user_id).gte("cooked_at", seven_days_ago).execute()
    
    cooked_recipes = res.data
    count = len(cooked_recipes)
    
    totals = {"Proteins": 0, "Carbs": 0, "Sugar": 0, "Vitamins": 0, "Salt": 0, "Fats": 0}
    for item in cooked_recipes:
        nut = get_recipe_nutrition(item["recipe_id"])
        if nut:
            for k in totals:
                totals[k] += (nut.get(k, 0) / 7.0)
                
    return {"count": count, "totals": totals}

def draw_nutrition_radar(totals, projected_recipe_nutrition=None):
    categories = ['Proteins', 'Carbs', 'Sugar', 'Vitamins', 'Salt', 'Fats']
    cats_loop = categories + [categories[0]]
    
    def to_list(d):
        return [d.get(c, 0) for c in categories] + [d.get(categories[0], 0)]
        
    actual_vals = to_list(totals)
    target_vals = [100] * 7
    
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=target_vals,
        theta=cats_loop,
        fill='none',
        name='Daily Target (100%)',
        line=dict(color='blue', dash='dash', width=2)
    ))
    fig.add_trace(go.Scatterpolar(
        r=actual_vals,
        theta=cats_loop,
        fill='toself',
        name='Daily Avg (Past 7 Days)',
        line=dict(color='red', width=2)
    ))
    if projected_recipe_nutrition:
        proj_vals = []
        for i, c in enumerate(categories):
            proj_vals.append(actual_vals[i] + projected_recipe_nutrition.get(c, 0))
        proj_vals.append(proj_vals[0])
        fig.add_trace(go.Scatterpolar(
            r=proj_vals,
            theta=cats_loop,
            fill='toself',
            name='+ This Recipe',
            line=dict(color='green', dash='dot', width=2)
        ))
        
    max_val = max(actual_vals) if not projected_recipe_nutrition else max(max(actual_vals), max(proj_vals))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, max(120, max_val * 1.2)])
        ),
        showlegend=True,
        margin=dict(l=40, r=40, t=40, b=40)
    )
    return fig
