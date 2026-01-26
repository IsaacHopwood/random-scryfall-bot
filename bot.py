import discord
from discord import app_commands
from discord.ext import tasks
import requests
import datetime
import asyncio

TOKEN = "MTQ2MzI2MjEzNDgwODA4ODY2Ng.GSuAOf.ew_5G3CMqF38X7iGelDQlzLWEtoNKVBEYpORsE"
DAILY_QUERY = None  # e.g. "is:commander" or leave None

# Dictionary to store scheduled channels: {channel_id: (hour, minute)}
scheduled_channels = {}
# Track which channels have been sent today: {channel_id: date}
sent_today = {}

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
    if not daily_check_task.is_running():
        daily_check_task.start()
        print("Daily check task started")
    print(f"Logged in as {client.user}")
    print(f"Currently scheduled channels: {len(scheduled_channels)}")

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

@tasks.loop(minutes=1)
async def daily_check_task():
    """Check every minute if it's time to send daily cards to any scheduled channels"""
    now = datetime.datetime.now()
    current_hour = now.hour
    current_minute = now.minute
    today = now.date()
    
    # Debug: log what we're checking
    if scheduled_channels:
        print(f"Checking scheduled channels at {current_hour:02d}:{current_minute:02d} - Scheduled: {list(scheduled_channels.items())}")
    
    # Check each scheduled channel
    for channel_id, (hour, minute) in list(scheduled_channels.items()):
        # Check if it's the right time AND we haven't sent to this channel today
        if current_hour == hour and current_minute == minute:
            # Skip if we already sent to this channel today
            if channel_id in sent_today and sent_today[channel_id] == today:
                print(f"Skipping channel {channel_id} - already sent today")
                continue
            
            print(f"Time match! Attempting to send to channel {channel_id} at {current_hour:02d}:{current_minute:02d}")
            channel = client.get_channel(channel_id)
            if channel is None:
                # Channel no longer exists, remove from schedule
                print(f"Channel {channel_id} not found, removing from schedule")
                del scheduled_channels[channel_id]
                if channel_id in sent_today:
                    del sent_today[channel_id]
                continue
            
            try:
                card = fetch_random_card(DAILY_QUERY)
                embed = build_embed(card)
                await channel.send("🌅 **Daily Random Card**", embed=embed)
                # Mark this channel as sent today
                sent_today[channel_id] = today
                print(f"✅ Sent daily card to channel {channel_id} at {current_hour:02d}:{current_minute:02d}")
            except Exception as e:
                print(f"❌ Error sending daily card to channel {channel_id}: {e}")
                import traceback
                traceback.print_exc()
                try:
                    await channel.send("Failed to fetch today's random card.")
                    sent_today[channel_id] = today  # Still mark as sent to prevent retries
                except Exception as e2:
                    # Channel might be deleted or bot doesn't have permission
                    print(f"❌ Error accessing channel {channel_id}: {e2}")
                    del scheduled_channels[channel_id]
                    if channel_id in sent_today:
                        del sent_today[channel_id]
    
    # Clean up old entries from sent_today (channels that are no longer scheduled)
    for channel_id in list(sent_today.keys()):
        if channel_id not in scheduled_channels:
            del sent_today[channel_id]

async def send_daily_card_immediate(channel_id: int, hour: int, minute: int, delay_seconds: float):
    """One-time task to send a daily card at a specific time (used when scheduling close to the target time)"""
    await asyncio.sleep(delay_seconds)
    
    # Double-check it's still scheduled and we haven't sent today
    if channel_id not in scheduled_channels:
        return
    
    scheduled_hour, scheduled_minute = scheduled_channels[channel_id]
    if scheduled_hour != hour or scheduled_minute != minute:
        return  # Schedule was changed
    
    now = datetime.datetime.now()
    today = now.date()
    
    if channel_id in sent_today and sent_today[channel_id] == today:
        return  # Already sent today
    
    channel = client.get_channel(channel_id)
    if channel is None:
        return
    
    try:
        card = fetch_random_card(DAILY_QUERY)
        embed = build_embed(card)
        await channel.send("🌅 **Daily Random Card**", embed=embed)
        sent_today[channel_id] = today
        print(f"✅ Sent daily card to channel {channel_id} via immediate task at {hour:02d}:{minute:02d}")
    except Exception as e:
        print(f"❌ Error in immediate task for channel {channel_id}: {e}")
        import traceback
        traceback.print_exc()

@daily_check_task.before_loop
async def before_daily_check_task():
    await client.wait_until_ready()

@tree.command(name="daily", description="Schedule the daily random card to be sent at a specific time in this channel")
@app_commands.describe(hour="Hour in 24-hour format (0-23)", minute="Minute (0-59)", cancel="Set to True to cancel daily messages in this channel")
async def daily_random(interaction: discord.Interaction, hour: int = None, minute: int = 0, cancel: bool = False):
    # Handle cancellation
    if cancel:
        if interaction.channel_id in scheduled_channels:
            del scheduled_channels[interaction.channel_id]
            await interaction.response.send_message("✅ Daily random card schedule cancelled for this channel.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ No daily schedule found for this channel.", ephemeral=True)
        return
    
    # Validate hour is provided when not canceling
    if hour is None:
        await interaction.response.send_message("❌ Please provide an hour (0-23) or set cancel to True.", ephemeral=True)
        return
    
    if hour < 0 or hour > 23:
        await interaction.response.send_message("❌ Hour must be between 0 and 23 (24-hour format).", ephemeral=True)
        return
    
    if minute < 0 or minute > 59:
        await interaction.response.send_message("❌ Minute must be between 0 and 59.", ephemeral=True)
        return
    
    # Store the channel and time in the schedule
    scheduled_channels[interaction.channel_id] = (hour, minute)
    
    # Check if the scheduled time is today and hasn't passed yet
    now = datetime.datetime.now()
    today = now.date()
    target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    # If the time is today and within the next 2 minutes, create a one-time task to ensure it sends
    if target_time.date() == today and now < target_time:
        time_until = (target_time - now).total_seconds()
        if time_until <= 120:  # Within 2 minutes
            print(f"Time is soon ({time_until:.1f}s), creating immediate task for channel {interaction.channel_id}")
            asyncio.create_task(send_daily_card_immediate(interaction.channel_id, hour, minute, time_until))
    
    time_str = f"{hour:02d}:{minute:02d}"
    print(f"Scheduled daily card for channel {interaction.channel_id} at {time_str}")
    await interaction.response.send_message(f"✅ Daily random card will be sent daily at **{time_str}** in this channel!", ephemeral=True)

client.run(TOKEN)
