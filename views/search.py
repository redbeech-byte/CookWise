import streamlit as st
from helpers.switch_page import switch_page
from helpers.db import search_recipes
from helpers.image_helper import display_recipe_image
from helpers.supabase_client import get_profile
from helpers.nutrition_helper import get_recipe_nutrition



def show():
    # Loading the user's profile from supabase lets the search page start with their saved
    # dietary restrictions and cooking preferences already applied
    # automatically using the current session user's id.
    profile = get_profile()
    profile_dietary = profile.get("dietary_restrictions", []) if profile else []
    profile_cooking = profile.get("cooking_preferences", []) if profile else []

    with st.container(border=True):
        # Keeping the search input wide and the filter button compact makes the
        # page feel like a normal recipe search interface.
        search_bar, spacer, filter_popover = st.columns([9, 1, 2], vertical_alignment="bottom")

        with search_bar:
            query = st.text_input("", placeholder="Enter ingredient, name, or keywords...")
            
        with filter_popover:
            # Putting filters in a popover keeps the page clean while still making
            # detailed search controls available.
            with st.popover("Filter", icon="🎯"):
                min_time, max_time = st.slider("Time Range (mins)", min_value=10, max_value=240, value=(10, 240), step=2)
                difficulty = st.selectbox("Difficulty", ["Any", "Easy", "Medium", "Hard"])
                
                st.write("Dietary Preferences")
                col1, col2 = st.columns(2)
                # Building dietary_prefs from checked boxes makes the selected
                # restrictions explicit before passing them into the database helper
                # preselected boxes based on the user's saved profile preferences
                dietary_prefs = []
                with col1:
                    if st.checkbox("Vegan", value="Vegan" in profile_dietary): dietary_prefs.append("Vegan")
                    if st.checkbox("Vegetarian", value="Vegetarian" in profile_dietary): dietary_prefs.append("Vegetarian")
                    if st.checkbox("Halal", value="Halal" in profile_dietary): dietary_prefs.append("Halal")
                with col2:
                    if st.checkbox("Gluten-Free", value="Gluten-Free" in profile_dietary): dietary_prefs.append("Gluten-Free")
                    if st.checkbox("Dairy-Free", value="Dairy-Free" in profile_dietary): dietary_prefs.append("Dairy-Free")
                    if st.checkbox("Nut-Free", value="Nut-Free" in profile_dietary): dietary_prefs.append("Nut-Free")
                
                if profile_cooking:
                    # Cooking preferences come from the profile automatically, so the
                    # user understands why search results may already be filtered.
                    st.info(f"Auto-applying cooking preferences: {', '.join(profile_cooking)}")
                    
        with st.spinner("Searching recipes..."):
            # Passing None for unchanged time boundaries keeps the database query
            # from filtering by the default slider limits unnecessarily.
            # this function is from the db helper and takes all the search parameters to return matching recipes from the database
            results = search_recipes(
                query=query, 
                limit=50, 
                max_time=max_time if max_time < 240 else None,
                min_time=min_time if min_time > 10 else None,
                difficulty=difficulty,
                dietary_prefs=dietary_prefs,
                cooking_prefs=profile_cooking
            )
    
    st.subheader(f"Results ({len(results)})")

    if results:
        # create a tiling grid for the search results,
        # Three cards per row gives each recipe enough room for image, title, and action button.
        cols_per_row = 3
        for i in range(0, len(results), cols_per_row):
            cols = st.columns(cols_per_row)
            for j in range(cols_per_row):
                if i + j < len(results):
                    recipe = results[i + j]
                    with cols[j]:
                        with st.container(border=True):
                            # The recipe id keeps image/display keys unique across cards.
                            # fetching and displaying the recipe image by title using the unique image helper from unsplash
                            display_recipe_image(recipe.get('recipe_title', 'recipe'), key_suffix=str(recipe['recipe_id']))
                            st.write(f"**{recipe.get('recipe_title')}**")
                            
                            # Triggering nutrition lookup warms the cache for recipes
                            # the user may open from the search results.
                            get_recipe_nutrition(recipe['recipe_id'])
                            
                            st.write(f"⏱️ {recipe.get('est_prep_time_min', 0)} mins")
                            # Opening a result stores the selected recipe through switch_page.
                            st.button(
                                "View Recipe", 
                                key=f"search_btn_{recipe['recipe_id']}",
                                use_container_width=True,
                                on_click=switch_page,
                                args=("Recipe Details", recipe['recipe_id']) # on click it will run the switch page function which recive the args to the recipe details page with the selected recipe id
                            )
    else:
        st.info("No recipes found.")
