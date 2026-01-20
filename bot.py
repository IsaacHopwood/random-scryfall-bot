import discord
from discord import app_commands
from discord.ext import tasks
import requests
import datetime
import asyncio

TOKEN = "MTQ2MzI2MjEzNDgwODA4ODY2Ng.GSuAOf.ew_5G3CMqF38X7iGelDQlzLWEtoNKVBEYpORsE"
DAILY_CHANNEL_ID = 829459386128269385  # <-- replace
DAILY_QUERY = None  # e.g. "is:commander" or leave None

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

def fetch_random_card(query=None):
    url = "https://api.scryfall.com/cards/random"
    if query:
        url += f"?q={query}"

    r = requests.get(url)
    r.raise_for_status()
    return r.json()

def build_embed(card):
    embed = discord.Embed(
        title=card["name"],
        description=card.get("oracle_text", "No oracle text."),
        url=card["scryfall_uri"]
    )

    if "image_uris" in card:
        embed.set_image(url=card["image_uris"]["normal"])
    elif "card_faces" in card:
        embed.set_image(url=card["card_faces"][0]["image_uris"]["normal"])

    embed.set_footer(text=f"{card['set_name']} • {card['rarity'].title()}")
    return embed

@client.event
async def on_ready():
    await tree.sync()
    daily_random.start()
    print(f"Logged in as {client.user}")

@tree.command(name="random", description="Pull a random Magic card from Scryfall")
@app_commands.describe(query="Optional Scryfall search query (e.g. is:commander)")
async def random_card(interaction: discord.Interaction, query: str = None):
    await interaction.response.defer()

    try:
        card = fetch_random_card(query)
        embed = build_embed(card)
        await interaction.followup.send(embed=embed)
    except Exception:
        await interaction.followup.send("Failed to fetch a card from Scryfall.")

@tasks.loop(hours=24)
async def daily_random():
    channel = client.get_channel(DAILY_CHANNEL_ID)
    if channel is None:
        return

    try:
        card = fetch_random_card(DAILY_QUERY)
        embed = build_embed(card)
        await channel.send("🌅 **Daily Random Card**", embed=embed)
    except Exception:
        await channel.send("Failed to fetch today’s random card.")

@daily_random.before_loop
async def before_daily_random():
    # Wait until bot is ready
    await client.wait_until_ready()

    # Schedule for next 9am local time (adjust as desired)
    now = datetime.datetime.now()
    target = now.replace(hour=9, minute=0, second=0, microsecond=0)

    if now >= target:
        target += datetime.timedelta(days=1)

    await asyncio.sleep((target - now).total_seconds())

client.run(TOKEN)
