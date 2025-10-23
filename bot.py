import os
import random
import asyncio
from dotenv import load_dotenv
import discord
from discord.ext import commands
from discord import app_commands
from PIL import Image, ImageDraw, ImageFont

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

MEME_FOLDER = "memes"
FONT_PATH = "impact.ttf"
QUOTES_FILE = "quotes.txt"
TEMP_OUTPUT = "temp_meme.png"

# Kanały, z których zapisujemy nowe wiadomości
ALLOWED_CHANNELS = [
    1110261477664882858,  # kanał 1
    1397291632440905888,  # kanał 2
]

# Kanały, z których pobieramy całą historię
HISTORY_CHANNELS = [
    1110261477664882858,  # kanał 1
    1203114412081418290,  # kanał 2
]

# Kanał, w którym bot będzie wysyłał memy automatycznie co 10 minut
AUTO_MEME_CHANNEL = 1430785590231699526

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Zapis wiadomości do pliku
def save_quote(text: str):
    text = text.strip()
    if not text:
        return
    existing = []
    if os.path.exists(QUOTES_FILE):
        with open(QUOTES_FILE, "r", encoding="utf-8") as f:
            existing = [line.strip() for line in f if line.strip()]
    if text in existing:
        return
    with open(QUOTES_FILE, "a", encoding="utf-8") as f:
        f.write(text + "\n")

# Pobranie historii wiadomości z listy kanałów
async def fetch_history():
    for channel_id in HISTORY_CHANNELS:
        channel = bot.get_channel(channel_id)
        if channel is None:
            print(f"⚠ Nie znalazłem kanału o ID {channel_id}")
            continue
        async for message in channel.history(limit=None):
            if not message.author.bot and not message.content.startswith("/"):
                save_quote(message.content)
        print(f"✅ Pobrano historię z kanału {channel.name}")

# Tworzenie mema z dopasowaniem tekstu do obrazu
def create_meme(base_path: str, text: str, output_path: str):
    img = Image.open(base_path).convert("RGBA")
    draw = ImageDraw.Draw(img)

    # ustawienia marginesów
    margin_x = 20
    margin_y = 20
    max_width = img.width - 2 * margin_x
    max_height = img.height - 2 * margin_y

    # początkowy duży font
    font_size = min(150, img.width // 6)
    try:
        font = ImageFont.truetype(FONT_PATH, font_size)
    except:
        font = ImageFont.load_default()

    # podział tekstu na linie i dopasowanie fontu
    while True:
        words = text.split()
        lines = []
        cur_line = ""
        for word in words:
            test_line = (cur_line + " " + word).strip()
            bbox = draw.textbbox((0,0), test_line, font=font)
            w = bbox[2] - bbox[0]
            if w <= max_width:
                cur_line = test_line
            else:
                if cur_line:
                    lines.append(cur_line)
                cur_line = word
        if cur_line:
            lines.append(cur_line)

        total_height = sum(draw.textbbox((0,0), line, font=font)[3] - draw.textbbox((0,0), line, font=font)[1] for line in lines) + (len(lines)-1)*5
        if total_height <= max_height or font_size <= 20:
            break
        font_size -= 2
        try:
            font = ImageFont.truetype(FONT_PATH, font_size)
        except:
            font = ImageFont.load_default()

    # rysowanie linii na obrazku
    y = margin_y + random.randint(0, max(0, max_height - total_height))
    for line in lines:
        bbox = draw.textbbox((0,0), line, font=font)
        w = bbox[2] - bbox[0]
        line_height = bbox[3] - bbox[1]
        x = margin_x + (max_width - w) // 2 + random.randint(-10, 10)
        # obrys czarny
        for dx in (-2, 2):
            for dy in (-2, 2):
                draw.text((x+dx, y+dy), line, font=font, fill="black")
        draw.text((x, y), line, font=font, fill="white")
        y += line_height + 5

    img.convert("RGB").save(output_path, "PNG")

# Zadanie automatyczne: generowanie mema co 10 minut
async def auto_meme_task():
    await bot.wait_until_ready()
    channel = bot.get_channel(AUTO_MEME_CHANNEL)
    if channel is None:
        print(f"⚠ Nie znalazłem kanału o ID {AUTO_MEME_CHANNEL}")
        return

    while not bot.is_closed():
        if not os.path.exists(QUOTES_FILE):
            await asyncio.sleep(600)
            continue

        with open(QUOTES_FILE, "r", encoding="utf-8") as f:
            quotes = [line.strip() for line in f if line.strip()]
        if not quotes:
            await asyncio.sleep(600)
            continue

        files = [f for f in os.listdir(MEME_FOLDER) if f.lower().endswith((".jpg", ".png"))]
        if not files:
            await asyncio.sleep(600)
            continue

        quote = random.choice(quotes)
        base = random.choice(files)
        base_path = os.path.join(MEME_FOLDER, base)
        create_meme(base_path, quote, TEMP_OUTPUT)

        await channel.send(file=discord.File(TEMP_OUTPUT))
        await asyncio.sleep(600)  # 10 minut

@bot.event
async def on_ready():
    print(f"✅ Zalogowano jako {bot.user} (ID: {bot.user.id})")
    await bot.tree.sync()
    await fetch_history()
    bot.loop.create_task(auto_meme_task())  # start automatycznego mema w tle

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if message.content.startswith("/"):
        return
    if message.channel.id not in ALLOWED_CHANNELS:
        return
    save_quote(message.content)
    await bot.process_commands(message)

@bot.tree.command(name="meme", description="Tworzy mema z losowego cytatu z kanałów")
async def meme(interaction: discord.Interaction):
    if not os.path.exists(QUOTES_FILE):
        await interaction.response.send_message("😕 Brak cytatów do wykorzystania.", ephemeral=True)
        return
    with open(QUOTES_FILE, "r", encoding="utf-8") as f:
        quotes = [line.strip() for line in f if line.strip()]
    if not quotes:
        await interaction.response.send_message("📭 Nie zapisano jeszcze żadnych cytatów.", ephemeral=True)
        return
    files = [f for f in os.listdir(MEME_FOLDER) if f.lower().endswith((".jpg", ".png"))]
    if not files:
        await interaction.response.send_message("📁 Brak obrazków w folderze memes.", ephemeral=True)
        return
    quote = random.choice(quotes)
    base = random.choice(files)
    base_path = os.path.join(MEME_FOLDER, base)
    create_meme(base_path, quote, TEMP_OUTPUT)
    await interaction.response.send_message(file=discord.File(TEMP_OUTPUT))

bot.run(TOKEN)
