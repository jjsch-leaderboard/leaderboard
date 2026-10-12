import os
import sqlite3
import threading
import aiohttp
import discord
from discord.ext import commands
from flask import Flask

# --- 1. FLASK KEEP-ALIVE WEBSERVER ---
app = Flask("")

@app.route("/")
def home():
    return "Leaderboard Bot is alive!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()

# --- 2. DISCORD BOT SETUP ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=["+", "?"], intents=intents)

BANNER_URL = "https://i.imgur.com/0yNuy7m.gif"

# --- 3. DATABASE SETUP & LEGACY PRELOAD ---
conn_lb = sqlite3.connect("leaderboard.db")
cursor_lb = conn_lb.cursor()

# Active Leaderboard Table
cursor_lb.execute("""
CREATE TABLE IF NOT EXISTS leaderboard (
    position INTEGER PRIMARY KEY,
    display_name TEXT,
    discord_id INTEGER,
    roblox_username TEXT,
    region TEXT,
    grade TEXT,
    clan_name TEXT DEFAULT 'None'
)
""")

# Permanent Legacy Leaderboard Table
cursor_lb.execute("""
CREATE TABLE IF NOT EXISTS legacy_leaderboard (
    position INTEGER PRIMARY KEY,
    display_name TEXT,
    discord_id INTEGER,
    roblox_username TEXT,
    region TEXT,
    grade TEXT,
    clan_name TEXT DEFAULT 'None'
)
""")
conn_lb.commit()

# Seed Legacy Leaderboard with Ranks 1-20
LEGACY_PLAYERS = [
    (1, "Furki", 0, "ReinhardReborn0", "Germany", "Special Grade", "None"),
    (2, "Noah", 0, "NotRealNoahHD", "Ireland", "Special Grade", "None"),
    (3, "Clipz", 0, "gcIipz", "United Kingdom", "Special Grade", "None"),
    (4, "Aiden", 0, "notaidenq", "Bulgaria", "Special Grade", "None"),
    (5, "Ego", 0, "sintelego", "Germany", "Special Grade", "None"),
    (6, "Ryze", 0, "rqrtxl", "United Kingdom", "Special Grade 1 High Strong", "None"),
    (7, "Emir", 0, "Emir09876321", "Türkiye", "Special Grade 1 High Strong", "None"),
    (8, "Zarif", 0, "zarif13413", "United Kingdom", "Special Grade 1 High Strong", "None"),
    (9, "Alie", 0, "Crpt_Ali", "United Kingdom", "Special Grade 1 High Weak", "None"),
    (10, "Vexxed", 0, "itsvexxed", "United Kingdom", "Special Grade 1 Mid Strong", "None"),
    (11, "Crucial", 0, "excrutiality", "United Kingdom", "Special Grade 1 Mid Strong", "None"),
    (12, "Scofield", 0, "di_0rr", "Netherlands", "Special Grade 1 Mid Strong", "None"),
    (13, "Aspect", 0, "Aspect_419", "Israel", "Special Grade 1 Mid Weak", "None"),
    (14, "Mrnobody", 0, "mrnobody6921", "United Kingdom", "Special Grade 1 Mid Weak", "None"),
    (15, "Hayat", 0, "MasterIndy05", "United Kingdom", "Special Grade 1 Low Strong", "None"),
    (16, "Vlue", 0, "likecutqhe", "Poland", "Special Grade 1 Low Stable", "None"),
    (17, "Mon", 0, "Blackfyre099", "Germany", "Special Grade 1 Low Stable", "None"),
    (18, "Psff0", 0, "psff_0", "United Kingdom", "Special Grade 1 Low Stable", "None"),
    (19, "Abu Bobby", 0, "abu_bobby8", "Germany", "Special Grade 1 Low Weak", "None"),
    (20, "NixtonFive", 0, "nixtonfivee", "France", "Special Grade 1 Low Weak", "None"),
]

for p in LEGACY_PLAYERS:
    cursor_lb.execute("""
    INSERT OR IGNORE INTO legacy_leaderboard (position, display_name, discord_id, roblox_username, region, grade, clan_name)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, p)
conn_lb.commit()

# --- 4. HELPER FUNCTIONS ---
async def get_roblox_data(username: str):
    async with aiohttp.ClientSession() as session:
        user_url = "https://users.roblox.com/v1/usernames/users"
        async with session.post(user_url, json={"usernames": [username]}) as resp:
            if resp.status != 200:
                return None, None
            u_data = await resp.json()
            if not u_data.get("data"):
                return None, None
            user_id = u_data["data"][0]["id"]

        thumb_url = f"https://thumbnails.roblox.com/v1/users/avatar-bust?userIds={user_id}&size=420x420&format=Png"
        async with session.get(thumb_url) as resp:
            avatar_url = None
            if resp.status == 200:
                t_data = await resp.json()
                if t_data.get("data"):
                    avatar_url = t_data["data"][0].get("imageUrl")
            
        return avatar_url, user_id

def reindex_leaderboard():
    cursor_lb.execute("SELECT rowid, * FROM leaderboard ORDER BY position ASC")
    rows = cursor_lb.fetchall()
    for index, row in enumerate(rows, start=1):
        cursor_lb.execute("UPDATE leaderboard SET position = ? WHERE rowid = ?", (index, row[0]))
    conn_lb.commit()

def build_card_description(d_mention, r_user, region, grade, clan_name):
    desc = f"« « | {d_mention} (`@{r_user}`) | » »\n**Region:** — {region}\n**Grade:** — {grade}"
    if clan_name and clan_name.strip() and clan_name.lower() != "none":
        desc += f"\n**Clan:** — {clan_name}"
    return desc

# --- 5. BOT EVENTS ---
@bot.event
async def on_ready():
    print(f"Leaderboard Bot ready as {bot.user.name}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s).")
    except Exception as e:
        print(f"Failed to sync slash commands: {e}")

# --- 6. LEADERBOARD SLASH COMMANDS ---

@bot.tree.command(name="leaderboard", description="Display the active leaderboard (Ranks 1-20)")
async def show_leaderboard(interaction: discord.Interaction):
    await interaction.response.defer()
    cursor_lb.execute("SELECT position, display_name, discord_id, roblox_username, region, grade, clan_name FROM leaderboard WHERE position BETWEEN 1 AND 20 ORDER BY position ASC")
    players = cursor_lb.fetchall()
    if not players:
        await interaction.followup.send("Active Leaderboard is currently empty.")
        return

    for pos, name, d_id, r_user, region, grade, clan_name in players:
        avatar_url, roblox_id = await get_roblox_data(r_user)
        profile_url = f"https://www.roblox.com/users/{roblox_id}/profile" if roblox_id else None
        d_mention = f"<@{d_id}>" if d_id and d_id != 0 else name

        description = build_card_description(d_mention, r_user, region, grade, clan_name)

        embed = discord.Embed(
            title=f"{name} | {pos}.",
            url=profile_url,
            description=description,
            color=discord.Color.dark_theme()
        )
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)
        if BANNER_URL:
            embed.set_image(url=BANNER_URL)
        await interaction.channel.send(embed=embed)

    await interaction.followup.send("Active Leaderboard (1-20) posted successfully!", ephemeral=True)

@bot.tree.command(name="legacy_leaderboard", description="Display the original Legacy Leaderboard")
async def show_legacy_leaderboard(interaction: discord.Interaction):
    await interaction.response.defer()
    cursor_lb.execute("SELECT position, display_name, discord_id, roblox_username, region, grade, clan_name FROM legacy_leaderboard ORDER BY position ASC")
    players = cursor_lb.fetchall()

    for pos, name, d_id, r_user, region, grade, clan_name in players:
        avatar_url, roblox_id = await get_roblox_data(r_user)
        profile_url = f"https://www.roblox.com/users/{roblox_id}/profile" if roblox_id else None
        d_mention = f"<@{d_id}>" if d_id and d_id != 0 else name

        description = build_card_description(d_mention, r_user, region, grade, clan_name)

        embed = discord.Embed(
            title=f"{name} | {pos}.",
            url=profile_url,
            description=description,
            color=discord.Color.dark_theme()
        )
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)
        if BANNER_URL:
            embed.set_image(url=BANNER_URL)
        await interaction.channel.send(embed=embed)

    await interaction.followup.send("📜 Legacy Leaderboard posted successfully!", ephemeral=True)

@bot.tree.command(name="add_player", description="Admin: Add a player to the active leaderboard")
@commands.has_permissions(administrator=True)
async def add_player(interaction: discord.Interaction, display_name: str, user: discord.Member, roblox_username: str, region: str, grade: str, clan_name: str = "None"):
    await interaction.response.defer(ephemeral=True)
    cursor_lb.execute("INSERT INTO leaderboard (display_name, discord_id, roblox_username, region, grade, clan_name) VALUES (?, ?, ?, ?, ?, ?)", (display_name, user.id, roblox_username, region, grade, clan_name))
    conn_lb.commit()
    reindex_leaderboard()
    await interaction.followup.send(f"Added **{display_name}** (`{roblox_username}`) to the leaderboard.")

@bot.tree.command(name="edit_player", description="Admin: Edit an existing player's details on the active leaderboard")
@commands.has_permissions(administrator=True)
async def edit_player(
    interaction: discord.Interaction,
    position: int,
    display_name: str = None,
    user: discord.Member = None,
    roblox_username: str = None,
    region: str = None,
    grade: str = None,
    clan_name: str = None
):
    await interaction.response.defer(ephemeral=True)

    cursor_lb.execute("SELECT display_name, discord_id, roblox_username, region, grade, clan_name FROM leaderboard WHERE position = ?", (position,))
    row = cursor_lb.fetchone()

    if not row:
        await interaction.followup.send(f"❌ No player found at rank #{position}.")
        return

    new_name = display_name if display_name is not None else row[0]
    new_d_id = user.id if user is not None else row[1]
    new_r_user = roblox_username if roblox_username is not None else row[2]
    new_region = region if region is not None else row[3]
    new_grade = grade if grade is not None else row[4]
    new_clan = clan_name if clan_name is not None else row[5]

    cursor_lb.execute("""
    UPDATE leaderboard 
    SET display_name = ?, discord_id = ?, roblox_username = ?, region = ?, grade = ?, clan_name = ?
    WHERE position = ?
    """, (new_name, new_d_id, new_r_user, new_region, new_grade, new_clan, position))
    conn_lb.commit()

    await interaction.followup.send(f"✏️ Updated player details for rank **#{position} ({new_name})**!")

@bot.tree.command(name="remove_player", description="Admin: Remove a player from the active leaderboard")
@commands.has_permissions(administrator=True)
async def remove_player(interaction: discord.Interaction, position: int):
    cursor_lb.execute("DELETE FROM leaderboard WHERE position = ?", (position,))
    conn_lb.commit()
    reindex_leaderboard()
    await interaction.response.send_message(f"Removed player at rank #{position}.", ephemeral=True)

@bot.tree.command(name="swap_players", description="Admin: Swap the positions of two players on the active leaderboard")
@commands.has_permissions(administrator=True)
async def swap_players(interaction: discord.Interaction, pos1: int, pos2: int):
    await interaction.response.defer(ephemeral=True)

    if pos1 == pos2:
        await interaction.followup.send("❌ Position 1 and Position 2 cannot be the same!")
        return

    cursor_lb.execute("SELECT display_name FROM leaderboard WHERE position = ?", (pos1,))
    p1 = cursor_lb.fetchone()

    cursor_lb.execute("SELECT display_name FROM leaderboard WHERE position = ?", (pos2,))
    p2 = cursor_lb.fetchone()

    if not p1 or not p2:
        await interaction.followup.send("❌ One or both position numbers were not found on the leaderboard.")
        return

    cursor_lb.execute("UPDATE leaderboard SET position = -1 WHERE position = ?", (pos1,))
    cursor_lb.execute("UPDATE leaderboard SET position = ? WHERE position = ?", (pos1, pos2))
    cursor_lb.execute("UPDATE leaderboard SET position = ? WHERE position = -1", (pos2,))
    conn_lb.commit()

    await interaction.followup.send(f"🔄 Swapped **#{pos1} ({p1[0]})** with **#{pos2} ({p2[0]})**!")

# --- 7. START BOT ---
keep_alive()
token = os.environ.get("DISCORD_TOKEN") or os.environ.get("LEADERBOARD_TOKEN")
bot.run(token)
