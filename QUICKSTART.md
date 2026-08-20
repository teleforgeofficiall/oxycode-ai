# OXYGENT Quick Start Guide

> Get your AI coding bot running in 5 minutes

---

## Prerequisites

- Python 3.10+ installed
- A Telegram account
- A Neon DB account (free tier available)

---

## Step 1: Create Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Name your bot (e.g., "OXYGENT AI")
4. Choose a username (e.g., "oxygent_ai_bot")
5. Copy the **bot token** (format: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

---

## Step 2: Create Database

1. Go to [neon.tech](https://neon.tech) and sign up (free)
2. Create a new project
3. Copy the **connection string** (looks like: `postgresql://user:password@ep-xxx.us-east-2.aws.neon.tech/dbname?sslmode=require`)

---

## Step 3: Configure Bot

1. Open the `MAIN BOT/` folder
2. Create a file named `.env`
3. Add this content:

```env
# From BotFather
BOT_TOKEN=your_bot_token_here

# Your Telegram user ID (send /start to @userinfobot to find it)
ADMIN_IDS=your_user_id_here

# From Neon DB
DATABASE_URL=your_neon_connection_string_here
```

---

## Step 4: Install & Run

Open terminal in the `MAIN BOT/` folder:

```bash
# Install dependencies
pip install -r requirements.txt

# Run the bot
python main.py
```

---

## Step 5: Test It

1. Open Telegram
2. Search for your bot username
3. Send `/start`
4. Send "Build a calculator in Python"

The bot will create a plan, ask for approval, then generate the code!

---

## Common Commands

| Command | What it does |
|---------|--------------|
| `/start` | Start the bot |
| `/menu` | Open main menu |
| `/status` | Check your limits |
| `/voice` | Enable voice replies |
| `/search python asyncio` | Web search |
| `/explain` | Explain pasted code |
| `/fix` | Debug broken code |

---

## Troubleshooting

**Bot doesn't respond:**
- Check BOT_TOKEN is correct
- Ensure bot is started in BotFather

**Database error:**
- Verify DATABASE_URL is correct
- Ensure Neon DB is not paused (free tier pauses after inactivity)

**"AI unavailable" message:**
- Free tier rate limit — wait 30 seconds and try again

---

## Next Steps

- Read [README.md](README.md) for full documentation
- Configure force-join channels via `/admin`
- Set up referrals for user growth
- Enable voice replies with `/voice`

---

**Need help?** Contact OXYCODE TEAM
