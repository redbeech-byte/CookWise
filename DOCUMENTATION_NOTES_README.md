# CookWise Documentation Notes — README

Purpose: this file is a working guide for documenting the CookWise application. It is not only about describing what the code does, but also about documenting important problems, edge cases, design choices, and fixes so that the final documentation explains why the code is written the way it is.

---

## Core documentation principle

When documenting this app, do not only write:
- what a function does

Also document:
- what problem it solves
- what bug or edge case led to this implementation
- what assumption the code makes
- what alternative was possible
- what could still be improved

Good documentation for this project should explain both:
1. behavior
2. reasoning

---

## Documentation style to use

Lawrence is a relative beginner, so the code should be documented a bit more explicitly than highly experienced developers might document it for themselves.

That means the documentation should:
- explain assumptions that an experienced coder might leave unstated
- explain why a line is written in a certain way when that is not obvious
- clarify edge cases and hidden failure modes
- help a beginner reconstruct the logic without guessing

At the same time, the documentation should still be:
- concise
- precise
- selective

So the goal is not to write huge walls of text everywhere.
The goal is to add explanation where it creates real understanding.

A good rule for this project is:
- document more than an expert would need
- but less than a tutorial would explain for every single line

### Preferred phrasing style

#### Quick comment style checklist
Before keeping a comment, ask:
- does it explain something the code alone may not make obvious?
- does it sound like a natural explanation instead of an instruction?
- would present tense make it read more smoothly here?
- is it short enough for normal flow?
- if it is longer, is that because it explains a real bug, workaround, or edge case?
- does it focus on one main idea?

For CookWise, comments should generally prefer:
- direct present-tense phrasing where it reads naturally
- active wording
- natural, readable sentences
- short explanatory comments over stiff command-style wording
- one clear idea per comment block

The revised `main_app.py` comments suggest the following style preferences:
- prefer comments that sound like explanations, not instructions to the reader
- use present tense especially for UI behavior, rendering behavior, and ongoing logic
- keep comments compact unless the code is solving a confusing bug or workaround
- avoid over-commenting obvious lines if the code already speaks clearly
- expand comments more when documenting a known issue, edge case, or workaround

Examples:
- preferred: `# Highlighting the active page button using the "primary" style.`
- less preferred: `# Highlight the active page button with the "primary" style.`
- preferred: `# Creating placeholder slots to avoid leftover UI elements when switching pages with different layouts.`
- less preferred: `# Create two placeholder slots and alternate between them on page changes.`

This is not a strict grammar rule, but a style preference for this project.
The present-tense version often feels more natural and less stiff while still staying precise.
It also fits well when the comment is describing what the code is currently doing during execution.

A useful distinction for this project:
- use brief present-tense comments for normal flow and UI behavior
- use longer explanatory comments when a line exists because of a past bug, confusing Streamlit behavior, or a portability issue

For important lines/functions, use comments or notes in this style:

```python
# Fall back to [] if the profile value is missing or None.
# Prevents: 'NoneType' object is not iterable.
dietary = profile.get("dietary_restrictions") or []
cooking = profile.get("cooking_preferences") or []
```

This style is good because it explains:
- what the line does
- why it is written this way
- what bug it prevents

---

## Example problem to document

## Recommendation helper — profile fields may be `None`

### Problem
In `recommendation_helper.py`, the code iterates over:
- `dietary_restrictions`
- `cooking_preferences`

The original logic used:

```python
dietary = profile.get("dietary_restrictions", [])
cooking = profile.get("cooking_preferences", [])
```

### Why this caused trouble
This only falls back to `[]` if the key is missing.
But if the key exists and its value is `None`, then the result is still `None`.

That means this later line can crash:

```python
for d in dietary:
```

with the error:

```text
'NoneType' object is not iterable
```

### Better version

```python
dietary = profile.get("dietary_restrictions") or []
cooking = profile.get("cooking_preferences") or []
```

### Why this works
Using `or []` handles both cases:
- missing value
- explicit `None`

### How we documented it
We decided to document it in a concise but explicit way:

```python
# Fall back to [] if the profile value is missing or None.
# Prevents: 'NoneType' object is not iterable.
dietary = profile.get("dietary_restrictions") or []
cooking = profile.get("cooking_preferences") or []
```

### Why this is a good documentation example
This is a strong example of the documentation style we want for CookWise because it:
- states the safeguard clearly
- names the concrete error being prevented
- stays short
- explains why the line is written this way without overexplaining it

### Important broader lesson
This was not just a one-off bug. It reflects a broader recurring mistake in the app:
- assuming a profile field or API/database value is a usable iterable/list
- when in reality it may be `None`

So this pattern should be watched throughout the application.
Whenever code assumes a list-like value, we should ask:
- could this be missing?
- could this be `None`?
- do we need a safe fallback like `or []`?

### Documentation note
This is exactly the kind of line where the documentation should mention the bug being prevented.

---

## Other important historical problems worth documenting

## 1. Streamlit rerun model causes hidden slowness

### Problem
The app felt slow, especially when switching pages.

### Root cause
The issue was not only “page switching.” The app was doing too much work during reruns:
- repeated Supabase reads
- repeated Unsplash image fetching
- nutrition loading/generation in list views
- recommendation logic rerun on page loads

### Why this matters for documentation
When documenting pages like `home.py`, `search.py`, and `profile.py`, note that:
- Streamlit reruns the script often
- heavy work inside render logic can hurt responsiveness
- certain design choices should be justified carefully

### Good documentation angle
Document which functions are cheap UI helpers and which ones are expensive data/API operations.

---

## 2. Nutrition helper mixed different conceptual time windows

### Problem
The NutriRadar originally used a 7-day averaging logic.
This made the chart feel misleading because a recipe cooked once got divided by 7.

### Why this was conceptually weak
The chart compared:
- daily target values
with
- 7-day averaged intake
which made the units feel inconsistent.

### New design direction
Shift toward:
- current intake over the last 24 hours
- or eventually intake for the current day
- compare that to a daily target
- project how one recipe affects that same scale

### Documentation angle
When documenting `nutrition_helper.py`, explicitly note:
- whether the logic is “past 7 days,” “last 24h,” or “today”
- why one time model was replaced by another
- that chart interpretation depends heavily on consistent units

---

## 3. NutriRadar labels became outdated when logic changed

### Problem
After changing the aggregation logic, some labels still said things like:
- `Weekly % DV`

while the code had already shifted toward a 24h interpretation.

### Documentation lesson
When changing logic, always check:
- function names
- chart legends
- subheaders
- comments
- UI wording

### Documentation angle
The code should explain not only what the chart draws, but also what time horizon the chart represents.

---

## 4. `target_vals = [100] * 7` was easy to misread

### Problem
It looked like “times seven days,” but that was wrong.

### Actual meaning
It creates a list of 7 values:

```python
[100, 100, 100, 100, 100, 100, 100]
```

### Why 7 values?
Because the radar chart needs:
- 6 categories
- plus 1 repeated first value to close the polygon

### Documentation angle
This is a good example of a line that needs explanation because the syntax is short but conceptually easy to misunderstand.

---

## 5. Saved recipes and cooked recipes are not structurally identical

### Problem
A remove button for cooked history did not work the same way as `remove_saved_recipe()`.

### Likely conceptual reason
- `saved_recipes` behaves more like a unique user-recipe relation
- `cooked_recipes` may contain multiple rows for the same recipe if cooked multiple times

### Documentation implication
When documenting delete functions, note whether deletion is by:
- `recipe_id`
- or unique row `id`

This matters because “remove this recipe from history” may mean:
- remove one occurrence
- or remove all occurrences

### Documentation angle
Clarify whether a table models:
- a unique relationship
- or an event/history log

---

## 6. `dashboard.py` exists but is not routed by `main_app.py`

### Problem
There is a dashboard file, but it is not used in the main page routing.

### Why it matters
Someone reading the code may assume it is part of the live app.
It currently appears to be:
- old
- standalone
- or experimental

### Documentation angle
Document clearly whether a file is:
- active in production flow
- experimental
- legacy/unconnected

---

## 7. `run_windows.bat` portability issues

### Problems encountered
- batch syntax errors
- stale launcher/path issues
- environment mismatch
- Windows trying to install macOS-only packages

### Key lessons
A professor-proof Windows launcher should:
- create its own venv
- use `python -m pip`
- use `python -m streamlit`
- avoid machine-specific assumptions
- use Windows-specific requirements file

### Documentation angle
Document deployment scripts separately from app logic.
They are part of usability and delivery, not only engineering.

---

## 8. Separate requirements files became necessary

### Problem
`requirements.txt` contained macOS-only dependencies:
- `pyobjc`
- `pyobjc-core`
- `pyobjc-framework-AVFoundation`
- `pyobjc-framework-Quartz`

This broke Windows setup.

### Solution direction
Split into:
- `requirements_windows.txt`
- `requirements_mac.txt`

### Documentation angle
Explain that dependency management can be platform-specific.
Do not present one requirements file as universally valid if it is not.

---

## 9. Streamlit secrets and local environment assumptions

### Problem
The app depends on `.streamlit/secrets.toml` for:
- Supabase credentials
- Gemini API keys

Without it, the app cannot run correctly.

### Documentation angle
Any “how to run” documentation must explicitly mention:
- where secrets go
- what keys are required
- what breaks if they are missing

---

## 10. Absolute paths were brittle and non-portable

### Problem
Hard-coded personal paths (for example for logo files or venvs) caused failures across machines.

### Better pattern
Use:
- relative paths
- `os.path.join(...)`
- local project-relative files

### Documentation angle
Whenever a path is written defensively or relatively, note that the goal is portability.

---

## Recommended documentation categories for the full app

When documenting the full app, try to classify code into these categories:

### A. UI / Navigation
Examples:
- `main_app.py`
- `switch_page.py`
- button callbacks

Document:
- what page is shown
- how navigation works
- why session state is needed

### B. Data access
Examples:
- `db.py`
- `supabase_client.py`

Document:
- what data source is used
- local DB vs remote Supabase
- what the table/function represents

### C. Intelligence / recommendation / estimation
Examples:
- `recommendation_helper.py`
- `nutrition_helper.py`
- `scan.py` / Gemini Vision integration

Document:
- what is truly machine learning / AI
- what is heuristic
- what is estimated
- what assumptions exist

### D. Visualization
Examples:
- NutriRadar / Plotly

Document:
- what each color means
- what time basis is used
- what the chart is intended to communicate
- what the limitations are

### E. Deployment / setup
Examples:
- `run_windows.bat`
- `run_mac.sh`
- requirements files

Document:
- platform assumptions
- venv logic
- dependency installation
- secrets requirements

---

## Good documentation questions to ask for each important function

For every major function, ask:

1. What does it do?
2. Why does it exist?
3. What inputs does it expect?
4. What outputs does it return?
5. What could go wrong?
6. What bug/edge case influenced this implementation?
7. What would a beginner misunderstand here?

If a function has an important edge case, document it.

---

## Whole-app understanding before file-by-file documentation

Before documenting individual files, it is important to refresh the understanding of the whole app so that documentation does not become siloed.

### Why this matters
A file may look simple in isolation while actually sitting inside a larger chain of dependencies.
For example:
- `home.py` displays the NutriRadar
- `nutrition_helper.py` computes the values and builds the chart
- `supabase_client.py` provides cooked history and profile data
- `db.py` provides recipe and ingredient data
- `recipe_details.py` and `guide.py` influence what gets viewed, cooked, and remembered
- `recommendation_helper.py` uses saved/cooked history and profile preferences to shape suggestions

If we document only one file at a time without keeping the overall system in mind, we risk writing comments that are locally correct but globally misleading.

### Current whole-app understanding of CookWise

At a high level, CookWise is built out of five interacting layers:

#### 1. Entry / navigation layer
Files:
- `main_app.py`
- `helpers/switch_page.py`

Role:
- login gate
- session state initialization
- page switching
- routing between views

#### 2. View layer
Files:
- `views/home.py`
- `views/search.py`
- `views/scan.py`
- `views/recipe_details.py`
- `views/profile.py`
- `views/guide.py`

Role:
- present the app to the user
- call helper functions
- display buttons, charts, cards, and forms

#### 3. Data access layer
Files:
- `helpers/db.py`
- `helpers/supabase_client.py`

Role:
- local recipe database access (`recipes.db`)
- remote user/profile/history access via Supabase
- saved/cooked/seen/profile state

#### 4. Intelligence / logic layer
Files:
- `helpers/recommendation_helper.py`
- `helpers/nutrition_helper.py`
- parts of `views/scan.py`

Role:
- recommendation logic
- nutrition estimation and aggregation
- image ingredient recognition via Gemini Vision

#### 5. Media / setup / portability layer
Files:
- `helpers/image_helper.py`
- `run_windows.bat`
- `run_mac.sh`
- requirements files

Role:
- recipe images from Unsplash
- attribution/tracking
- local launch/setup
- platform-specific dependency handling

### Important interdependencies to remember

#### NutriRadar chain
The NutriRadar is not “just in one file.” It depends on a chain:

```text
home.py / recipe_details.py
    ↓
get_today_nutrition() or related nutrition aggregation
    ↓
supabase_client.py (cooked history, profile)
    ↓
db.py + recipe_nutrition data
    ↓
draw_nutrition_radar()
```

This means any documentation of the radar should mention:
- where the displayed data comes from
- what time window is used
- what assumptions the chart is making
- what file is responsible for computation vs display

#### Recommendation chain
Recommendations also depend on several files together:

```text
home.py
    ↓
recommendation_helper.py
    ↓
get_saved_recipes() / get_cooked_recipes() / get_profile()
    ↓
supabase_client.py
    ↓
recipe feature loading from DB / Supabase
```

This means recommendation comments should not pretend it is pure ML in isolation.
It depends on user history, profile fields, recipe features, and safe handling of missing values.

#### Profile/history chain
The profile page is not just UI. It is a control surface for:
- saved recipes
- cooked history
- preference settings
- security/account actions

Changes here affect:
- recommendations
- NutriRadar history
- app personalization

### Practical documentation rule from this
When documenting a file, always ask:
- what other files feed data into this one?
- what files depend on this one afterward?
- is this file computing, displaying, storing, or routing?

If the answer involves multiple files, mention that dependency in the documentation.

### Current NutriRadar-specific understanding
This is especially important because the NutriRadar changed multiple times.

At the moment, key points to document are:
- whether the radar is based on today, the last 24 hours, or a broader historical window
- whether the target line is a daily target
- whether the green projection means “today + this meal” or something else
- whether the values come from actual tracked recipes, cached nutrition, or Gemini-estimated nutrition

This should be documented consistently across:
- function names
- comments
- labels
- chart legends
- page subtitles

### Documentation goal
The point of this whole-app understanding is to prevent silo thinking.
We are not documenting disconnected files.
We are documenting one app made of interdependent pieces.

## Final reminder

The goal of documentation is not to make the code look more complicated.
The goal is to make the codebase:
- understandable
- explainable in presentation or hand-in context
- easier to maintain
- easier to defend when asked “why is it written like this?”

For CookWise especially, documenting the reason behind the structure is almost as important as documenting the structure itself.
