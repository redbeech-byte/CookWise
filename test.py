from helpers.supabase_client import get_cooked_recipes, get_recipe_by_id
import streamlit as st

print("get_cooked_recipes:", get_cooked_recipes()[0])