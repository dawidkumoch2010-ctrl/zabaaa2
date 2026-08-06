import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio
from datetime import datetime
import os
import threading
import aiohttp
from flask import Flask

# --- KONFIGURACJA SERWERA WWW (FLASK) ---
app = Flask(__name__)
bot_status = "Uruchamianie..."

@app.route("/")
def home():
    return f"Status bota: {bot_status}"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- KONFIGURACJA BOTA ---
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# --- FUNKCJA DO POBIERANIA HISTORII ---
async def send_transcript_dm(member: discord.Member, channel: discord.TextChannel):
    """Pobiera historię i wysyła na DM użytkownika."""
    messages = []
    async for message in channel.history(limit=100, oldest_first=True):
        if not message.author.bot: # Pomijamy boty, żeby było czytelniej
            messages.append(f"**{message.author.display_name}**: {message.content}")
    
    transcript_text = "\n".join(messages) if messages else "Brak treści do wyświetlenia."
    
    # Ucinamy, jeśli tekst przekracza limit Discorda (4096 znaków)
    if len(transcript_text) > 4000:
        transcript_text = transcript_text[-4000:] 
        transcript_text = "...(historia zbyt długa, wyświetlam końcówkę)...\n" + transcript_text

    embed = discord.Embed(
        title=f"📜 Historia rozmowy z ticketa: {channel.name}",
        description=transcript_text,
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    
    try:
        await member.send(embed=embed)
        return True
    except discord.Forbidden:
        return False

# --- RESZTA LOGIKI (POZOSTAŁE FUNKCJE) ---

async def send_log(guild, message):
    log_channel = discord.utils.get(guild.text_channels, name="📑-logi")
    if log_channel:
        embed = discord.Embed(title="⚙️ SYSTEM LOGS", description=message, color=discord.Color.dark_grey(), timestamp=datetime.now())
        await log_channel.send(embed=embed)

def has_management_permission(member: discord.Member) -> bool:
    if member == member.guild.owner or member.guild_permissions.administrator: return True
    allowed_keywords = ["szef", "zarząd", "rekruter"]
    for role in member.roles:
        if any(keyword in role.name.lower() for keyword in allowed_keywords): return True
    return False

@tasks.loop(minutes=10)
async def keep_alive_ping():
    url = os.environ.get("RENDER_EXTERNAL_URL")
    if url:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    print(f"⏰ Ping wysłany do {url}")
        except: pass

class PodanieModal(discord.ui.Modal, title="📝 Formularz Podania"):
    q1 = discord.ui.TextInput(label="1. Nick z Minecrafta", style=discord.TextStyle.short, required=True, max_length=32)
    q2 = discord.ui.TextInput(label="2. Ile masz lat?", style=discord.TextStyle.short, required=True, max_length=10)
    q9 = discord.ui.TextInput(label="9. Podaj 3 ostatnie gildie", style=discord.TextStyle.paragraph, required=True, max_length=200)
    q10 = discord.ui.TextInput(label="10. Dlaczego my?", style=discord.TextStyle.paragraph, required=True, max_length=300)
    q13 = discord.ui.TextInput(label="13. Czy znasz kogoś?", style=discord.TextStyle.short, required=True, max_length=100)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.user.edit(nick=self.q1.value.strip())
        embed = discord.Embed(title=f"📋 PODANIE — {interaction.user.display_name}", color=discord.Color.blue())
        embed.add_field(name="Nick", value=self.q1.value, inline=False)
        embed.add_field(name="Wiek", value=self.q2.value, inline=False)
        embed.add_field(name="Gildie", value=self.q9.value, inline=False)
        embed.add_field(name="Dlaczego my?", value=self.q10.value, inline=False)
        embed.add_field(name="Znasz kogoś?", value=self.q13.value, inline=False)
        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("✅ Podanie wysłane!", ephemeral=True)
        await send_log(interaction.guild, f"📝 Nowe podanie od {interaction.user.mention}")

# (Wstaw tutaj resztę klas: PodanieTicketView, TicketView, VerifyView, AdminDashboard, SendEmbedModal, KlepaView z poprzedniego kodu)
# Dla przejrzystości pomijam je w tym bloku, ale pamiętaj, żeby zostawić je w kodzie!

@bot.event
async def on_ready():
    global bot_status
    bot_status = f"Zalogowany jako {bot.user}"
    print(f"✅ Bot online: {bot.user}")
    if not keep_alive_ping.is_running(): keep_alive_ping.start()

@bot.event
async def setup_hook():
    # Pamiętaj o dodaniu wszystkich widoków tutaj:
    bot.add_view(AdminDashboard())
    bot.add_view(VerifyView())
    bot.add_view(TicketView())
    bot.add_view(KlepaView())
    bot.add_view(PodanieTicketView())
    await bot.tree.sync()

# --- POPRAWIONE KOMENDY /ACC ORAZ /ODRZ ---

@bot.tree.command(name="acc", description="Akceptuje podanie i przesyła historię do Ciebie na DM")
async def acc(interaction: discord.Interaction):
    if not has_management_permission(interaction.user):
        await interaction.response.send_message("❌ Brak uprawnień!", ephemeral=True)
        return

    # Szukamy kandydata
    target = None
    for obj, overwrite in interaction.channel.overwrites.items():
        if isinstance(obj, discord.Member) and not obj.bot and obj != interaction.user:
            target = obj
            break

    if not target:
        await interaction.response.send_message("❌ Nie znaleziono kandydata na tym kanale!", ephemeral=True)
        return

    # Zarządzanie rolami
    r_czlonek = discord.utils.get(interaction.guild.roles, name="「 」Członek")
    if r_czlonek: await target.add_roles(r_czlonek)
    
    # Wyślij transkrypt do Ciebie
    success = await send_transcript_dm(interaction.user, interaction.channel)
    
    embed = discord.Embed(title="🎉 PODANIE ZAAKCEPTOWANE!", description=f"Kandydat {target.mention} został przyjęty!", color=discord.Color.green())
    if not success: embed.add_field(name="⚠️ Uwaga:", value="Nie udało się wysłać transkryptu na DM (masz zablokowane DM).")
    
    await interaction.response.send_message(embed=embed)
    await send_log(interaction.guild, f"✅ {target.mention} przyjęty przez {interaction.user.mention}. Historia wysłana na DM rekrutera.")

@bot.tree.command(name="odrz", description="Odrzuca podanie i przesyła historię do kandydata na DM")
async def odrz(interaction: discord.Interaction):
    if not has_management_permission(interaction.user):
        await interaction.response.send_message("❌ Brak uprawnień!", ephemeral=True)
        return

    target = None
    for obj, overwrite in interaction.channel.overwrites.items():
        if isinstance(obj, discord.Member) and not obj.bot and obj != interaction.user:
            target = obj
            break

    if not target:
        await interaction.response.send_message("❌ Nie znaleziono kandydata!", ephemeral=True)
        return

    # Wyślij transkrypt do kandydata
    success = await send_transcript_dm(target, interaction.channel)
    
    embed = discord.Embed(title="❌ PODANIE ODRZUCONE", description=f"Podanie gracza {target.mention} zostało odrzucone.", color=discord.Color.red())
    if not success: embed.add_field(name="⚠️ Uwaga:", value="Nie udało się wysłać transkryptu na DM gracza (ma zablokowane DM).")
    
    await interaction.response.send_message(embed=embed)
    await send_log(interaction.guild, f"❌ {target.mention} odrzucony przez {interaction.user.mention}. Historia wysłana na DM kandydata.")

# --- RESZTA KOMEND (/zamknij, /klepa itp.) zostaje bez zmian ---

if __name__ == "__main__":
    TOKEN = os.environ.get("DISCORD_TOKEN")
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
    bot.run(TOKEN)
