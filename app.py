import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(
    page_title="Recipe Guide Prototype",
    page_icon="🍽️",
    layout="wide"
)

# ----------------------------
# Load recipe data
# ----------------------------
@st.cache_data

def load_data():
    return pd.read_csv("recipes_extended.csv")


df = load_data()

possible_name_cols = ["title", "recipe_name", "name", "RecipeName"]
recipe_col = None
for col in possible_name_cols:
    if col in df.columns:
        recipe_col = col
        break
if recipe_col is None:
    recipe_col = df.columns[0]

recipe_names = df[recipe_col].dropna().astype(str).unique().tolist()

# ----------------------------
# Session state
# ----------------------------
if "page" not in st.session_state:
    st.session_state.page = "welcome"

if "user_name" not in st.session_state:
    st.session_state.user_name = ""

if "cooked_recipes" not in st.session_state:
    st.session_state.cooked_recipes = []

if "selected_recipe" not in st.session_state:
    st.session_state.selected_recipe = None

if "intent_mode" not in st.session_state:
    st.session_state.intent_mode = None

# ----------------------------
# Helper functions
# ----------------------------
def go_to(page_name):
    st.session_state.page = page_name


def add_cooked_recipe(recipe_name):
    st.session_state.cooked_recipes.append(
        {
            "recipe": recipe_name,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
    )


def find_recipe_row(recipe_name):
    recipe_data = df[df[recipe_col].astype(str) == str(recipe_name)]
    if recipe_data.empty:
        return None
    return recipe_data.iloc[0]


# ----------------------------
# Sidebar
# ----------------------------
st.sidebar.title("Prototype Navigation")
st.sidebar.write(f"Current page: **{st.session_state.page}**")

if st.session_state.user_name:
    st.sidebar.success(f"Signed in as: {st.session_state.user_name}")
else:
    st.sidebar.info("No user signed in yet")

st.sidebar.divider()

if st.sidebar.button("Welcome"):
    go_to("welcome")
if st.sidebar.button("Intent Page"):
    go_to("intent")
if st.sidebar.button("Nutrition Overview"):
    go_to("nutrition")
if st.sidebar.button("Recommendations"):
    go_to("recommendations")
if st.sidebar.button("Cooking Guide"):
    go_to("cooking")

st.sidebar.divider()
st.sidebar.subheader("Cooked history")
if st.session_state.cooked_recipes:
    cooked_df = pd.DataFrame(st.session_state.cooked_recipes)
    st.sidebar.dataframe(cooked_df, use_container_width=True)
else:
    st.sidebar.caption("No recipes cooked yet")

# ----------------------------
# Page: Welcome / Sign-in
# ----------------------------
if st.session_state.page == "welcome":
    st.title("Recipe Guide Prototype")
    st.subheader("Entry Experience")
    st.write(
        "A first Streamlit prototype of the intended app flow: sign-in, intent, nutrition overview, recommendation, and cooking guidance."
    )

    st.markdown("### Welcome")
    st.write("This screen should feel calm, clean, and easy to enter.")

    user_name = st.text_input("Enter your name / profile", value=st.session_state.user_name)

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Continue into app"):
            st.session_state.user_name = user_name.strip()
            go_to("intent")
            st.rerun()
    with col2:
        if st.button("Use demo user"):
            st.session_state.user_name = "Demo User"
            go_to("intent")
            st.rerun()

    st.divider()
    st.caption("UX goal: low-friction entry, simple sign-in, immediate sense of continuity.")

# ----------------------------
# Page: Intent / Chatbot start
# ----------------------------
elif st.session_state.page == "intent":
    st.title("What would you like to cook today?")
    st.subheader("Intent Page")

    if st.session_state.user_name:
        st.write(f"Welcome back, **{st.session_state.user_name}**.")

    st.info(
        "Chatbot-style prompt: Do you already know what you want to cook, or would you like suggestions based on your recent nutrition?"
    )

    choice = st.radio(
        "Choose your path",
        [
            "I already know what I want to cook",
            "I want suggestions based on my nutrition this week"
        ]
    )

    if choice == "I already know what I want to cook":
        st.session_state.intent_mode = "known_recipe"
        selected_recipe = st.selectbox("Choose a recipe", recipe_names)
        st.session_state.selected_recipe = selected_recipe

        if st.button("Go to cooking flow"):
            go_to("cooking")
            st.rerun()

    else:
        st.session_state.intent_mode = "needs_suggestion"
        if st.button("Show my current nutrition overview"):
            go_to("nutrition")
            st.rerun()

# ----------------------------
# Page: Nutrition overview
# ----------------------------
elif st.session_state.page == "nutrition":
    st.title("Current Nutrition Overview")
    st.subheader("Weekly nutrition picture")

    st.write(
        "This screen represents the weekly nutrition overview based on cooked recipes. In the real app, this would be connected to nutritional values from cooked recipes."
    )

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("### Spider / radar visualization placeholder")
        st.write(
            "This is where the spider chart from `nutrition_spider_demo.html` should be integrated or recreated in Streamlit."
        )
        spider_placeholder = pd.DataFrame(
            {
                "Nutrition Dimension": ["Protein", "Fats", "Salt", "Vitamins", "Sugar", "Carbs"],
                "Current Weekly Score": [65, 80, 55, 40, 75, 60]
            }
        )
        st.dataframe(spider_placeholder, use_container_width=True)

    with col2:
        st.markdown("### Quick interpretation")
        st.write("- Protein looks moderate")
        st.write("- Vitamins appear relatively low")
        st.write("- Sugar appears comparatively high")
        st.write("- This page should help the user decide what makes sense next")

    if st.button("Show recipe suggestions"):
        go_to("recommendations")
        st.rerun()

# ----------------------------
# Page: Recommendations
# ----------------------------
elif st.session_state.page == "recommendations":
    st.title("Suggested Recipes")
    st.subheader("Recipes that may improve the current balance")

    st.write(
        "In the full version, these recommendations should come from the nutritional profile and later possibly from ML logic."
    )

    suggested_recipes = recipe_names[:3] if len(recipe_names) >= 3 else recipe_names

    for recipe in suggested_recipes:
        with st.container(border=True):
            st.markdown(f"### {recipe}")
            st.write("Why this could fit: helps move the user toward a more balanced weekly profile.")
            if st.button(f"Select {recipe}", key=f"select_{recipe}"):
                st.session_state.selected_recipe = recipe
                go_to("cooking")
                st.rerun()

# ----------------------------
# Page: Cooking guide
# ----------------------------
elif st.session_state.page == "cooking":
    st.title("Cooking Guidance")
    st.subheader("Guided cooking flow")

    if not st.session_state.selected_recipe:
        st.warning("No recipe selected yet. Please select a recipe first.")
        if st.button("Back to intent page"):
            go_to("intent")
            st.rerun()
    else:
        st.success(f"Selected recipe: {st.session_state.selected_recipe}")

        recipe_row = find_recipe_row(st.session_state.selected_recipe)

        if recipe_row is not None:
            st.markdown("### Recipe overview")
            st.dataframe(pd.DataFrame([recipe_row]), use_container_width=True)
        else:
            st.info("Recipe details could not be loaded from the dataset.")

        st.markdown("### Cooking mode placeholder")
        st.write("In the later version, this section should guide the user step by step through the cooking process.")
        st.write("Possible future elements:")
        st.write("- ingredient checklist")
        st.write("- step-by-step instructions")
        st.write("- progress tracker")
        st.write("- chatbot-style cooking guidance")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Mark recipe as cooked"):
                add_cooked_recipe(st.session_state.selected_recipe)
                st.success("Recipe saved to cooked history.")
        with col2:
            if st.button("Back to recommendations"):
                go_to("recommendations")
                st.rerun()

        st.divider()
        st.caption(
            "UX goal: after recipe selection, the app becomes a calm and practical cooking assistant."
        )
