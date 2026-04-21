import streamlit as st
import sqlite3
import json
import plotly.graph_objects as go
import google.generativeai as genai
from helpers.db import DB_PATH, get_recipe_by_id, get_ingredients_for_recipe
from helpers.supabase_client import supabase, get_current_user
import datetime

# Configure Gemini
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

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
    Do not include any other text or markdown formatting like ```json.
    """
    
    # We use a cheap models
    model = genai.GenerativeModel("gemini-2.5-flash-lite")
    try:
        response = model.generate_content(prompt)
        text = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(text)
        
        # Save to DB
        with get_db_connection() as conn:
            conn.execute("""
                INSERT INTO recipe_nutrition (recipe_id, proteins, carbs, sugar, vitamins, salt, fats)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (str(recipe_id), data.get("Proteins", 0), data.get("Carbs", 0), data.get("Sugar", 0), data.get("Vitamins", 0), data.get("Salt", 0), data.get("Fats", 0)))
        
        return data
    except Exception as e:
        print(f"Error evaluating nutrition: {e}")
        return {"Proteins": 0, "Carbs": 0, "Sugar": 0, "Vitamins": 0, "Salt": 0, "Fats": 0}

def get_past_7_days_nutrition():
    user = get_current_user()
    if not user or not user.user:
        return {"count": 0, "totals": {"Proteins": 0, "Carbs": 0, "Sugar": 0, "Vitamins": 0, "Salt": 0, "Fats": 0}}
    
    seven_days_ago = (datetime.datetime.now() - datetime.timedelta(days=7)).isoformat()
    res = supabase.table("cooked_recipes").select("recipe_id").eq("user_id", user.user.id).gte("cooked_at", seven_days_ago).execute()
    
    cooked_recipes = res.data
    count = len(cooked_recipes)
    
    totals = {"Proteins": 0, "Carbs": 0, "Sugar": 0, "Vitamins": 0, "Salt": 0, "Fats": 0}
    for item in cooked_recipes:
        nut = get_recipe_nutrition(item["recipe_id"])
        if nut:
            for k in totals:
                # Accumulate weekly fraction (% DV / 700 * 100 = fraction of weekly target in percentage)
                # simpler: % DV / 7 = percentage of weekly target
                totals[k] += (nut.get(k, 0) / 7.0)
                
    return {"count": count, "totals": totals}

def draw_nutrition_radar(totals, projected_recipe_nutrition=None):
    categories = ['Proteins', 'Carbs', 'Sugar', 'Vitamins', 'Salt', 'Fats']
    cats_loop = categories + [categories[0]]
    
    def to_list(d):
        return [d.get(c, 0) for c in categories] + [d.get(categories[0], 0)]
        
    actual_vals = to_list(totals)
    target_vals = [100] * 7 # 100% of daily target
    
    fig = go.Figure()
    
    # 100% Target Ring (WHO recommendation)
    fig.add_trace(go.Scatterpolar(
        r=target_vals,
        theta=cats_loop,
        fill='none',
        name='Daily Target (100%)',
        line=dict(color='blue', dash='dash', width=2)
    ))
    
    # Current Actual
    fig.add_trace(go.Scatterpolar(
        r=actual_vals,
        theta=cats_loop,
        fill='toself',
        name='Daily Avg (Past 7 Days)',
        line=dict(color='red', width=2)
    ))
    
    # Projected
    if projected_recipe_nutrition:
        # Show expected daily total (avg + this recipe)
        proj_vals = []
        for i, c in enumerate(categories):
            proj_vals.append(actual_vals[i] + projected_recipe_nutrition.get(c, 0))
        proj_vals.append(proj_vals[0]) # Loop it
        
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
            radialaxis=dict(
                visible=True,
                range=[0, max(120, max_val * 1.2)]
            )
        ),
        showlegend=True,
        margin=dict(l=40, r=40, t=40, b=40)
    )
    return fig

