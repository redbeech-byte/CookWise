import streamlit as st
import textwrap
import os
from helpers.switch_page import switch_page
from helpers.db import search_recipes, get_recipe_by_id
from helpers.image_helper import display_recipe_image, get_unique_recipe_image_data
from helpers.supabase_client import get_cooked_recipes, mark_recipe_seen
from helpers.recommendation_helper import get_recommended_recipes
from helpers.nutrition_helper import get_past_7_days_nutrition, draw_nutrition_radar, get_todays_nutrition, get_recipe_nutrition



def show():
    # Reading the logged-in user id from session state lets the home page load
    # user-specific history and nutrition data.
    user_id = st.session_state.get("user_id")
    
    # Pre-fetching the main home-page data inside one spinner keeps the page from
    # showing several separate loading messages during Streamlit reruns.
    with st.spinner("Loading your kitchen..."):
        cooked_recipes = get_cooked_recipes()
        # The blue radar layer uses a 7-day representative daily quality, not a raw weekly total.
        avg_info = get_past_7_days_nutrition(user_id)
        # The red radar layer shows actual progress strictly for today.
        today_info = get_todays_nutrition(user_id)
    
    # Keeping the current guide id in session state lets the user continue a recipe
    # after navigating away from the cooking guide.
    current_guide_id = st.session_state.get("current_recipe_guide")

    # The home layout puts the NutriRadar on the left and the navigation/continue
    # card on the right.
    graph, spacer1, navigation, spacer2 = st.columns([4, 0.5, 2, 0.5])

    # A orientation, welcome panel with quick access to continue the latest recipe
    with navigation:
        with st.container():
            # First-time users have no cooking history and no active guide yet, so
            # the home page gives them a simple starting point.
            if not current_guide_id and not cooked_recipes:
                st.subheader("Welcome to CookWise! 👋")
                st.write("Your personalized cooking assistant. Get started by searching for recipes or uploading your fridge ingredients.")
            elif not current_guide_id and cooked_recipes:
                # If the user has cooked before but has no active guide, showing the
                # latest cooked recipe gives them a useful shortcut back into the app.
                st.subheader("Welcome back! 👋")
                st.write("Here's the last recipe you cooked:")
                last_cooked_id = cooked_recipes[0]["recipe_id"]
                last_cooked = get_recipe_by_id(last_cooked_id)
                if last_cooked:
                    title = last_cooked.get('recipe_title', 'Unknown Title')
                    display_recipe_image(title, key_suffix="last_cooked")
                    st.write(f"**{title}**")
                    
                    # Continuing from here opens the guide for the last cooked recipe.
                    st.button(
                        "👨‍🍳 Continue Cooking", 
                        key="continue_cooking", 
                        use_container_width=True,
                        on_click=switch_page,
                        args=("Guide", last_cooked_id, lambda: mark_recipe_seen(last_cooked_id))
                    )
                    # Viewing details gives the user recipe context before entering the guide.
                    st.button(
                        "View Recipe Details", 
                        key="view_details", 
                        use_container_width=True,
                        on_click=switch_page,
                        args=("Recipe Details", last_cooked_id, lambda: mark_recipe_seen(last_cooked_id))
                    )
            else:
                # An active guide takes priority over general history because it means
                # the user left a cooking session unfinished.
                st.subheader("Continue where you left off:")
                last_cooked = get_recipe_by_id(current_guide_id)
                if last_cooked:
                    title = last_cooked.get('recipe_title', 'Unknown Title')
                    display_recipe_image(title, key_suffix="current_guide")
                    st.write(f"**{title}**")
                    # Continuing from here resumes the guide already stored in session state.
                    st.button(
                        "👨‍🍳 Continue Cooking", 
                        key="continue_cooking_guide", 
                        use_container_width=True,
                        on_click=switch_page,
                        args=("Guide", current_guide_id, lambda: mark_recipe_seen(current_guide_id))
                    )
                    st.button(
                        "View Recipe Details", 
                        key="view_details_guide", 
                        use_container_width=True,
                        on_click=switch_page,
                        args=("Recipe Details", current_guide_id, lambda: mark_recipe_seen(current_guide_id))
                    )

    # The NutriRadar is a key home-page feature that gives users a visual snapshot of their nutrition history and today's progress.
    with graph:
        st.subheader("Your NutriRadar")
        with st.container(border=True):
            # Drawing today's actual intake together with the representative daily
            # quality gives the user both current progress and recent context.
            fig = draw_nutrition_radar(
                today_stats=today_info["totals"],
                average_stats=avg_info["totals"]
            )
            st.plotly_chart(fig, use_container_width=True, config={'staticPlot': True}) # make sure it is not interactive

    # Recommendations are the main home-page discovery feature and are based on
    # saved/cooked history plus profile preferences.
    recipes = get_recommended_recipes(limit=12)
    if not recipes:
        # Falling back to a filtered search keeps the carousel populated when the
        # recommendation model has too little data or returns no matches.
        profile = get_profile()
        dietary = profile.get("dietary_restrictions", []) if profile else []
        cooking = profile.get("cooking_preferences", []) if profile else []
        recipes = search_recipes("", limit=12, dietary_prefs=dietary, cooking_prefs=cooking)

    # Preloading images before rendering the carousel reduces the grey-loading feel
    # when recipe cards appear.
    for r in recipes:
        get_unique_recipe_image_data(r.get('recipe_title', 'recipe'))

    # The carousel index is stored in session state so it survives Streamlit reruns
    # The index is which 4 of the 12 recipes are currently displayed
    if "carousel_idx" not in st.session_state:
        st.session_state.carousel_idx = 0

    st.divider()
    st.subheader("Recommended Recipes")
    # Four tiles keep the carousel dense while still leaving enough space for images and titles.
    TILES_PER_ROW = 4

    col_prev, col_content, col_next = st.columns([1, 15, 1], vertical_alignment="center")

    # the button to spin the carousel to the left
    with col_prev:
        def prev_carousel():
            # Modulo wrapping lets the carousel loop from the first item back to the last.
            st.session_state.carousel_idx = (st.session_state.carousel_idx - 1) % len(recipes)
        st.button("◀", width='stretch', on_click=prev_carousel, key="carousel_prev")

    with col_content:
        # Selecting a window of recipes from the carousel index creates the visible row.
        current_recipes = []
        for i in range(TILES_PER_ROW):
            idx = (st.session_state.carousel_idx + i) % len(recipes)
            current_recipes.append(recipes[idx])
        
        card_cols = st.columns(len(current_recipes))
        
        # zip is a convenient way to iterate over the current recipes and their corresponding column containers in parallel
        for col, recipe in zip(card_cols, current_recipes):
            rid = recipe.get("recipe_id")
            with col:
                with st.container(border=True):
                    title = recipe.get("recipe_title", "Unknown Title")
                    
                    # fetching and displaying the recipe image by title using the unique image helper from unsplash
                    display_recipe_image(title, key_suffix=f"home_{rid}")
                    
                    # Estimating title height keeps cards in the same row visually aligned
                    # even when recipe names have different lengths.
                    max_chars_per_line = 12
                    estimated_lines = len(textwrap.wrap(title, width=max_chars_per_line)) or 1
                    st.subheader(title)
                    
                    max_title_lines = 4
                    pad_lines = max(0, max_title_lines - estimated_lines)
                    for _ in range(pad_lines):
                        st.write(f"\n")
                        
                    st.write(f"⏱️ **{recipe.get('est_prep_time_min', 0)} mins**")
                    st.write("")
                    
                    # Triggering nutrition lookup warms the cache for recipes
                    # the user may open from the recommended list.
                    get_recipe_nutrition(rid)
                    
                    # Marking the recipe as seen when opening it helps recommendation
                    # history reflect what the user has already viewed.
                    st.button(
                        "View Recipe", 
                        key=f"btn_{rid}", 
                        use_container_width=True,
                        on_click=switch_page,
                        args=("Recipe Details", rid, lambda r=rid: mark_recipe_seen(r)) # using a lambda to capture the current recipe id in the loop for the on_click callback
                    )
    # the button to spin the carousel to the right
    with col_next:
        def next_carousel():
            # Modulo wrapping lets the carousel continue from the last item back to the first.
            st.session_state.carousel_idx = (st.session_state.carousel_idx + 1) % len(recipes)
        st.button("▶", width='stretch', on_click=next_carousel, key="carousel_next")
