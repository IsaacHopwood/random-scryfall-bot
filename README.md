Dependencies:
--mac
python -m pip install -U discord.py requests python-dotenv

--windows
py -m pip install -U discord.py requests python-dotenv

Setup:
1. Copy .env.example to .env
2. Add your Discord bot token to .env:
   DISCORD_BOT_TOKEN=your_token_here
3. Run the bot: python bot.py (or py bot.py on Windows)
