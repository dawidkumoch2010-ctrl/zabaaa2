import discord
from discord.ext import commands
import asyncio
from datetime import datetime
import os
import threading
from flask import Flask, render_template_string

# --- KONFIGURACJA SERWERA WWW I BOTA ---
app = Flask(__name__)
bot_status = "Uruchamianie..."

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# --- WZÓR PODANIA ---
WZOR_PODANIA = """**WZÓR PODANIA**
➞ 1. Nick z Minecrafta »
➞ 2. Ile masz lat? »
➞ 3. Dzienna aktywność »
➞ 4. Od kiedy grasz gildie »
➞ 5. Twoje PvP od 1 do 10 »
➞ 6. Co robisz gdy zginiesz na przebicie? »
➞ 7. Kiedy kończysz edycję? »
➞ 8. Czy drzesz mordę na kanale podczas klepy »
➞ 9. Podaj 3 ostatnie gildię »
➞ 10. Dlaczego my? » 
➞ 11. Skille (slime/water) »
➞ 12. Staty (Mogą być SS) »
➞ 13. Słuchasz liderówki? » 
➞ 14. Znasz kogoś? »
➞ 15. Na ile zostajesz? »
➞ 16. Doświadczenie 1.16 »
➞ 17. Toksyczność/Dystans »"""

async def send_log(guild, message):
    log_channel = discord.utils.get(guild.text_channels, name="📑-logi")
    if log_channel:
        embed = discord.Embed(title="⚙️ SYSTEM LOGS", description=message, color=discord.Color.dark_grey(), timestamp=datetime.now())
        await log_channel.send(embed=embed)

# --- WIDOKI ---

class TicketView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    
    @discord.ui.button(label="Otwórz Ticket", style=discord.ButtonStyle.primary, emoji="🎫", custom_id="persistent:open_v35")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        cat = discord.utils.get(guild.categories, name="『ETAP 1』")
        
        # Pobieranie ról do uprawnień kanału
        r_ticket = discord.utils.get(guild.roles, name="Ticket")
        r_zarzad = discord.utils.get(guild.roles, name="Zarząd")
        r_test_zarzad = discord.utils.get(guild.roles, name="Test Zarząd")
        r_szef = discord.utils.get(guild.roles, name="「 」SZEF")

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        
        # Automatyczne dodawanie uprawnień dla rang zarządzających do KAŻDEGO ticketu
        roles_to_add = [r_ticket, r_zarzad, r_test_zarzad, r_szef]
        for role in roles_to_add:
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        channel = await guild.create_text_channel(f"🎫-{interaction.user.name}", category=cat, overwrites=overwrites)
        await interaction.response.send_message(f"✅ Ticket stworzony: {channel.mention}", ephemeral=True)
        await channel.send(embed=discord.Embed(title="📋 FORMULARZ", description=WZOR_PODANIA, color=0x3498db))

class VerifyView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    
    @discord.ui.button(label="Zacznij Rekrutację", style=discord.ButtonStyle.success, emoji="⚔️", custom_id="persistent:verify_v35")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = discord.utils.get(interaction.guild.roles, name="║ do rekru")
        if role: await interaction.user.add_roles(role)
        await interaction.response.send_message("✅ Nadano rangę do rekrutacji!", ephemeral=True)

class AdminDashboard(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    
    @discord.ui.select(
        placeholder="Zarządzaj gildią...",
        custom_id="persistent:admin_v35",
        options=[
            discord.SelectOption(label="BUDUJ WSZYSTKO (FULL SETUP)", value="setup", emoji="🏗️"),
            discord.SelectOption(label="Wyślij Weryfikację", value="ver", emoji="🛡️"),
            discord.SelectOption(label="Wyślij Tickety", value="tick", emoji="🎫"),
            discord.SelectOption(label="Wyczyść czat", value="clear", emoji="🧹"),
            discord.SelectOption(label="NUKE SERVER", value="nuke", emoji="☢️")
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        guild = interaction.guild
        ev = guild.default_role

        if select.values[0] == "setup":
            await interaction.response.send_message("🚀 Buduję strukturę z uwzględnieniem Zarządu i Ticketów...", ephemeral=True)
            
            # --- ROLE ---
            roles_data = {
                "「 」SZEF": 0x992d22, 
                "Zarząd": 0x740909, 
                "Test Zarząd": 0xe67e22, 
                "Rekruter": 0x3498db, 
                "Ticket": 0x00ffff, 
                "「 」Członek": 0x9b59b6, 
                "🤝 Sojusz": 0xf1c40f, 
                "║ do rekru": 0x2ecc71
            }
            r = {}
            for n, c in roles_data.items():
                role = discord.utils.get(guild.roles, name=n) or await guild.create_role(name=n, color=discord.Color(c), hoist=True)
                r[n] = role
            
            # --- UPRAWNIENIA ---
            p_member = {
                ev: discord.PermissionOverwrite(view_channel=False), 
                r["「 」Członek"]: discord.PermissionOverwrite(view_channel=True), 
                r["🤝 Sojusz"]: discord.PermissionOverwrite(view_channel=True), 
                r["「 」SZEF"]: discord.PermissionOverwrite(view_channel=True)
            }
            
            # Rangi widzące rekrutację (w tym Ticket, Zarząd, Test Zarząd)
            p_rekru = {
                ev: discord.PermissionOverwrite(view_channel=False),
                r["「 」Członek"]: discord.PermissionOverwrite(view_channel=False),
                r["Ticket"]: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
                r["Rekruter"]: discord.PermissionOverwrite(view_channel=True),
                r["Test Zarząd"]: discord.PermissionOverwrite(view_channel=True),
                r["Zarząd"]: discord.PermissionOverwrite(view_channel=True),
                r["「 」SZEF"]: discord.PermissionOverwrite(view_channel=True),
                r["║ do rekru"]: discord.PermissionOverwrite(view_channel=True)
            }

            # Logi ukryte dla Test Zarządu
            p_logs = {
                ev: discord.PermissionOverwrite(view_channel=False),
                r["Ticket"]: discord.PermissionOverwrite(view_channel=False),
                r["Test Zarząd"]: discord.PermissionOverwrite(view_channel=False),
                r["Zarząd"]: discord.PermissionOverwrite(view_channel=True),
                r["「 」SZEF"]: discord.PermissionOverwrite(view_channel=True)
            }

            # --- KANAŁY ---
            c_w = await guild.create_category("・ 『Witaj/Żegnaj』 ・")
            await guild.create_text_channel("💻-witamy", category=c_w)
            await guild.create_text_channel("💬-żegnamy", category=c_w)

            c_i = await guild.create_category("・ 『Informacje』 ・", overwrites=p_member)
            await guild.create_text_channel("📢-ogłoszenia", category=c_i)
            await guild.create_text_channel("🚫-regulamin", category=c_i)

            c_v = await guild.create_category("・ 『Weryfikacja』 ・")
            await guild.create_text_channel("🛡️-weryfikacja", category=c_v)

            c_c = await guild.create_category("・ 『Strefa Chatu』 ・", overwrites=p_member)
            await guild.create_text_channel("💬-chat", category=c_c)
            await guild.create_text_channel("📷-multimedia", category=c_c)

            c_d = await guild.create_category("・ 『Dane Gildii』 ・", overwrites=p_member)
            await guild.create_text_channel("📜-kordy", category=c_d)
            await guild.create_text_channel("📝-formułki", category=c_d)

            c_vo = await guild.create_category("・ 『Kanały Głosowe』 ・", overwrites=p_member)
            await guild.create_voice_channel("🔊-Gadanko 1", category=c_vo)
            await guild.create_voice_channel("🔊-Gadanko 2", category=c_vo)

            # --- SEKCJA REKRUTACJI ---
            c_r = await guild.create_category("・ 『Rekrutacja』 ・", overwrites=p_rekru)
            await guild.create_text_channel("🎫-ticket", category=c_r)
            await guild.create_voice_channel("🔊-Rekru 1", category=c_r, user_limit=2)
            await guild.create_voice_channel("🔊-Rekru 2", category=c_r, user_limit=2)

            await guild.create_category("『ETAP 1』", overwrites=p_rekru)
            await guild.create_category("『ETAP 2』", overwrites=p_rekru)
            await guild.create_category("『ARCHIWUM』", overwrites=p_rekru)

            # --- ADMIN ---
            c_a = await guild.create_category("・ 『Administracja』 ・", overwrites={ev: discord.PermissionOverwrite(view_channel=False)})
            await guild.create_text_channel("📑-logi", category=c_a, overwrites=p_logs)
            await guild.create_text_channel("⚙-panel", category=c_a, overwrites=p_logs)
            
            await interaction.followup.send("✅ System zbudowany! Zarząd i Ticket widzą wszystko.", ephemeral=True)

        elif select.values[0] == "ver": await interaction.channel.send(embed=discord.Embed(title="🛡️ WERYFIKACJA", color=0x2ecc71), view=VerifyView())
        elif select.values[0] == "tick": await interaction.channel.send(embed=discord.Embed(title="🎫 REKRUTACJA", color=0x3498db), view=TicketView())
        elif select.values[0] == "clear": await interaction.channel.purge(limit=100)
        elif select.values[0] == "nuke":
            if interaction.user == guild.owner:
                for c in guild.channels: await c.delete()
                await guild.create_text_channel("nuke-done")

# --- BOT EVENTS ---

@bot.event
async def on_ready():
    global bot_status
    bot_status = f"Zalogowany jako {bot.user}"
    print(f"✅ Bot online: {bot.user}")

@bot.event
async def setup_hook():
    bot.add_view(AdminDashboard()); bot.add_view(VerifyView()); bot.add_view(TicketView())

@bot.command()
@commands.has_permissions(administrator=True)
async def dashboard(ctx):
    await ctx.send(embed=discord.Embed(title="🖥️ PANEL STEROWANIA", color=0x5865F2), view=AdminDashboard())

@bot.command()
async def acc(ctx):
    target = discord.utils.get(ctx.guild.categories, name="『ETAP 2』")
    role_ticket = discord.utils.get(ctx.guild.roles, name="Ticket")
    role_mention = role_ticket.mention if role_ticket else "@Ticket"
    
    if target and "🎫-" in ctx.channel.name:
        await ctx.channel.edit(category=target)
        await ctx.send(f"Etap 2 {role_mention} jak ktoś będzie miał czas to ci odpisze w sprawie duel wtedy udaj sie na kanal <#1494791287533076603> lub <#1494791290569621685>")

@bot.command()
async def final(ctx):
    if "🎫-" in ctx.channel.name:
        u_name = ctx.channel.name.replace("🎫-", "")
        member = discord.utils.get(ctx.guild.members, name=u_name)
        r_cz = discord.utils.get(ctx.guild.roles, name="「 」Członek")
        r_re = discord.utils.get(ctx.guild.roles, name="║ do rekru")
        if member:
            if r_cz: await member.add_roles(r_cz)
            if r_re: await member.remove_roles(r_re)
            await ctx.channel.set_permissions(member, view_channel=False)
        archive = discord.utils.get(ctx.guild.categories, name="『ARCHIWUM』")
        if archive: await ctx.channel.edit(category=archive)
        await ctx.send("👑 **FINAŁ.** Ticket zarchiwizowany.")

@bot.command()
async def odrz(ctx):
    if "🎫-" in ctx.channel.name: await ctx.channel.delete()


# --- PANEL WWW (FLASK) ---
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <title>Panel Bota Discord</title>
    <style>
        body { font-family: Arial, sans-serif; background: #0f172a; color: #f8fafc; text-align: center; padding: 60px; }
        .card { background: #1e293b; max-width: 450px; margin: 0 auto; padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); border: 1px solid #334155; }
        .status { color: #22c55e; font-weight: bold; font-size: 1.2em; }
    </style>
</head>
<body>
    <div class="card">
        <h1>Panel Sterowania Botem</h1>
        <p>Status bota: <span class="status">{{ status }}</span></p>
        <p style="color: #94a3b8; font-size: 9pt;">Strona internetowa działa 24/7 w chmurze razem z botem!</p>
    </div>
</body>
</html>
'''

@app.route("/")
def home():
    return render_template_string(HTML_TEMPLATE, status=bot_status)

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# --- URUCHOMIENIE APLIKACJI ---
if __name__ == "__main__":
    TOKEN = os.environ.get("DISCORD_TOKEN")
    
    if not TOKEN:
        print("❌ BŁĄD: Nie znaleziono zmiennej DISCORD_TOKEN w ustawieniach Rendera!")
    else:
        t = threading.Thread(target=run_flask)
        t.start()
        bot.run(TOKEN)
