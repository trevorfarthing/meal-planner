# Weekly Meal Planner — GitHub Action + Claude + Telegram

Automatically picks 4–5 dinner recipes every Saturday, builds a grocery list,
and sends both to a Telegram chat.

## Repository Structure

```
├── .github/
│   └── workflows/
│       └── weekly-meal-plan.yml   # GitHub Action (runs every Saturday 9 AM PT)
├── scripts/
│   ├── generate_meal_plan.py      # Calls Claude API, builds plan + grocery list
│   └── send_telegram.py           # Sends formatted message to Telegram
├── recipes/                       # Your Recipe Keeper exports go here
│   ├── chicken-alfredo.html
│   ├── beef-tacos.txt
│   └── ...
├── meal-plan-history.json         # Rolling 8-week history (auto-updated by Action)
└── README.md
```

## Setup

### 1. Create a Telegram Bot

1. Open Telegram and search for **@BotFather**.
2. Send `/newbot` and follow the prompts to name your bot.
3. BotFather will give you a **bot token** — save this.
4. Create a group chat with your wife, then add the bot to the group.
5. To get the **chat ID**, send a message in the group, then visit:
   ```
   https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   ```
   Look for `"chat": {"id": -XXXXXXXXX}` — that negative number is your chat ID.
   For a DM, message the bot directly and check the same endpoint.

### 2. Get an Anthropic API Key

1. Go to [console.anthropic.com](https://console.anthropic.com/).
2. Create an API key under **API Keys**.
3. Add some credits (the meal planner uses Claude Sonnet — typically costs
   a few cents per run depending on how many recipes you have).

### 3. Set Up the GitHub Repository

1. Create a **private** repo on GitHub.
2. Copy this folder structure into it.
3. Export your recipes from Recipe Keeper (Settings → Export in the app).
   Unzip and put the recipe files in the `recipes/` folder.
4. Copy the `meal-plan-history.json` starter file into the repo root
   (or let the script create a blank one on first run).

### 4. Add Repository Secrets

Go to your repo → **Settings → Secrets and variables → Actions** and add:

| Secret Name          | Value                                    |
| -------------------- | ---------------------------------------- |
| `ANTHROPIC_API_KEY`  | Your Anthropic API key (`sk-ant-...`)    |
| `TELEGRAM_BOT_TOKEN` | Bot token from BotFather                 |
| `TELEGRAM_CHAT_ID`   | Numeric chat ID (e.g., `-1001234567890`) |

### 5. Test It

- Go to **Actions** tab in your repo.
- Click **Weekly Meal Plan** in the left sidebar.
- Click **Run workflow** → **Run workflow** to trigger it manually.
- Check the action logs and your Telegram chat.

### 6. Customize

Edit these parts of `scripts/generate_meal_plan.py` to match your household:

- **`SYSTEM_PROMPT`** — pantry staples list, number of proteins, cuisine
  preferences, serving size, etc.
- **`load_recipes()`** — if your Recipe Keeper export uses a different
  folder structure or file format, adjust the glob patterns.
- **Cron schedule** — in `.github/workflows/weekly-meal-plan.yml`, adjust
  the cron expression if you want a different day/time. The default is
  Saturday 9 AM Pacific (17:00 UTC during PDT).

## How It Works

1. **Load** — reads all recipe files from `recipes/` and the last 8 weeks
   of history from `meal-plan-history.json`.
2. **Plan** — sends everything to Claude Sonnet with instructions to pick
   4–5 recipes with ingredient overlap, protein variety, and no repeats.
   Claude returns structured JSON.
3. **Save** — appends the new week to the history file and commits it back
   to the repo.
4. **Notify** — formats the plan as a readable Telegram message with the
   meal schedule and a grocery checklist, then sends it to your chat.

## Cost

Each weekly run uses roughly 2,000–8,000 input tokens (depending on how
many recipes you have) and ~500–1,000 output tokens. At Claude Sonnet
pricing this works out to a few cents per week.

## Adding New Recipes

Just add new files to the `recipes/` folder and push to the repo. The
next weekly run will automatically include them in the selection pool.
