#!/usr/bin/env python3
"""
generate_meal_plan.py

Reads recipe files and history, calls the Claude API to select this week's
meals, writes the updated history and a plan summary for Telegram.
"""

import json
import os
import glob
from datetime import datetime, timedelta
from pathlib import Path

import anthropic


# ---------------------------------------------------------------------------
# 1. Load recipe files
# ---------------------------------------------------------------------------

def load_recipes(recipe_dir: str = "recipes") -> str:
    """Read all recipe files and concatenate into a single text block."""
    recipe_texts = []
    extensions = ["*.html", "*.htm", "*.txt", "*.json", "*.md"]

    for ext in extensions:
        for filepath in sorted(glob.glob(os.path.join(recipe_dir, "**", ext), recursive=True)):
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            recipe_texts.append(f"--- FILE: {os.path.basename(filepath)} ---\n{content}\n")

    if not recipe_texts:
        raise FileNotFoundError(f"No recipe files found in {recipe_dir}/")

    return "\n".join(recipe_texts)


# ---------------------------------------------------------------------------
# 2. Load history
# ---------------------------------------------------------------------------

HISTORY_FILE = "meal-plan-history.json"


def load_history() -> dict:
    """Load the meal plan history or create a blank one."""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return {"_schema": {}, "weeks": []}


# ---------------------------------------------------------------------------
# 3. Build the Claude prompt
# ---------------------------------------------------------------------------

def get_next_monday() -> str:
    """Return the ISO date of the upcoming Monday."""
    today = datetime.now()
    days_ahead = 7 - today.weekday()  # Monday = 0
    if today.weekday() == 0:
        days_ahead = 7  # If today is Monday, target next Monday
    # If running on Saturday (5), days_ahead = 2 → upcoming Monday
    next_mon = today + timedelta(days=(7 - today.weekday()) % 7 or 7)
    # Simpler: always target the Monday after today
    if today.weekday() < 5:  # Mon-Fri: this coming Monday might be past
        next_mon = today + timedelta(days=-today.weekday(), weeks=1)
    else:
        next_mon = today + timedelta(days=(7 - today.weekday()))
    return next_mon.strftime("%Y-%m-%d")


SYSTEM_PROMPT = """\
You are a meal planning assistant. You will receive a collection of recipes \
and a JSON history of recent weekly meal plans. Your job is to select 4–5 \
dinner recipes for the upcoming week and produce a structured JSON response.

SELECTION RULES:
- Do NOT repeat any recipe from the last 2 weeks in the history.
- Maximize ingredient overlap between selected recipes to reduce grocery cost.
- Include at least 2 different proteins (chicken, beef, pork, shrimp, salmon, turkey, etc.).
- Vary cuisine styles (don't pick all Italian or all Mexican).
- Prefer weeknight-friendly meals (under 45 min active cooking).
- Assign recipes to Monday–Thursday plus optionally one weekend day (Fri/Sat/Sun).
- Leave 1–2 weekend days unassigned (we eat out).

PANTRY STAPLES (do NOT include in the grocery list):
Salt, black pepper, olive oil, vegetable oil, butter, garlic powder, \
onion powder, paprika, cumin, chili powder, Italian seasoning, red pepper flakes, \
soy sauce, hot sauce, Worcestershire sauce, sugar, flour, baking soda, baking powder, \
rice.

GROCERY LIST RULES:
- Combine duplicate ingredients across recipes.
- Round up quantities for sensible store purchases.
- Remove pantry staples listed above.

Respond with ONLY valid JSON (no markdown fences, no preamble) matching this structure:
{
  "weekStart": "YYYY-MM-DD",
  "createdAt": "ISO datetime",
  "recipes": [
    {
      "name": "Recipe Name",
      "assignedDay": "Monday",
      "primaryProtein": "chicken",
      "cuisineStyle": "Italian",
      "ingredients": ["ingredient 1", "ingredient 2"]
    }
  ],
  "groceryList": [
    {
      "item": "Ingredient name",
      "quantity": "2 lbs",
      "forRecipes": ["Recipe A", "Recipe B"]
    }
  ],
  "notes": "Brief notes about ingredient overlap, substitutions, etc."
}
"""


def build_user_message(recipes_text: str, history: dict, week_start: str) -> str:
    """Build the user message with recipes and history context."""

    # Only include last 3 weeks of history to save tokens
    recent_weeks = history.get("weeks", [])[-3:]
    history_summary = json.dumps(recent_weeks, indent=2) if recent_weeks else "No previous weeks."

    return f"""\
Plan meals for the week starting {week_start}.

## Recent History (last {len(recent_weeks)} weeks)
{history_summary}

## Available Recipes
{recipes_text}
"""


# ---------------------------------------------------------------------------
# 4. Call Claude
# ---------------------------------------------------------------------------

def call_claude(system: str, user_message: str) -> dict:
    """Call the Anthropic API and parse the JSON response."""
    client = anthropic.Anthropic()  # Uses ANTHROPIC_API_KEY env var

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )

    text = response.content[0].text.strip()

    # Strip markdown fences if Claude adds them despite instructions
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    text = text.strip()

    return json.loads(text)


# ---------------------------------------------------------------------------
# 5. Update history
# ---------------------------------------------------------------------------

def update_history(history: dict, new_week: dict) -> dict:
    """Append new week and trim to last 8 entries."""
    history["weeks"].append(new_week)
    history["weeks"] = history["weeks"][-8:]
    return history


# ---------------------------------------------------------------------------
# 6. Format Telegram message
# ---------------------------------------------------------------------------

def format_telegram_message(plan: dict) -> str:
    """Create a nicely formatted Telegram message."""
    lines = []
    lines.append(f"🍽 *Meal Plan — Week of {plan['weekStart']}*\n")

    # Recipes by day
    for recipe in plan["recipes"]:
        emoji = {
            "Monday": "1️⃣", "Tuesday": "2️⃣", "Wednesday": "3️⃣",
            "Thursday": "4️⃣", "Friday": "5️⃣", "Saturday": "6️⃣", "Sunday": "7️⃣"
        }.get(recipe["assignedDay"], "📌")
        lines.append(f"{emoji} *{recipe['assignedDay']}:* {recipe['name']}")
        lines.append(f"    _{recipe['cuisineStyle']} · {recipe['primaryProtein']}_")

    # Grocery list
    lines.append(f"\n🛒 *Grocery List ({len(plan['groceryList'])} items)*\n")
    for item in plan["groceryList"]:
        recipes_str = ", ".join(item["forRecipes"])
        lines.append(f"• {item['item']} — {item['quantity']}")
        lines.append(f"    _({recipes_str})_")

    # Notes
    if plan.get("notes"):
        lines.append(f"\n📝 {plan['notes']}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7. Main
# ---------------------------------------------------------------------------

def main():
    print("Loading recipes...")
    recipes_text = load_recipes()
    print(f"Loaded recipes ({len(recipes_text)} chars)")

    print("Loading history...")
    history = load_history()
    print(f"History has {len(history.get('weeks', []))} weeks")

    week_start = get_next_monday()
    print(f"Planning for week of {week_start}")

    user_message = build_user_message(recipes_text, history, week_start)

    print("Calling Claude API...")
    plan = call_claude(SYSTEM_PROMPT, user_message)
    print(f"Got plan with {len(plan['recipes'])} recipes")

    # Ensure weekStart matches what we asked for
    plan["weekStart"] = week_start
    if "createdAt" not in plan:
        plan["createdAt"] = datetime.now().isoformat()

    # Update and save history
    history = update_history(history, plan)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)
    print("History updated")

    # Format and save Telegram message
    telegram_msg = format_telegram_message(plan)
    with open("telegram_message.txt", "w") as f:
        f.write(telegram_msg)
    print("Telegram message saved")

    # Also save the raw plan for debugging
    with open("current_plan.json", "w") as f:
        json.dump(plan, f, indent=2)
    print("Done!")


if __name__ == "__main__":
    main()
