import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio
from datetime import datetime
import os
import threading
import aiohttp
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

# --- MECHANIZM KEEP-ALIVE (SAMOPINGOWANIE CO 10 MINUT) ---
@tasks.loop(minutes=10)
async def keep_alive_ping():
    url = os.environ.get("RENDER_EXTERNAL_URL")
    if url:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    print(f"⏰ [KEEP-ALIVE] Ping wysłany do {url} | Status: {response.status}")
        except Exception as e:
            print(f"⚠️ [KEEP-ALIVE] Błąd podczas wysyłania pinga: {e}")

# --- MODALE (FORMULARZE OKIENKOWE) ---

class SendEmbedModal(discord.ui.Modal, title="📩 Wyślij wiadomość w ramce"):
    channel_id = discord.ui.TextInput(
        label="ID Kanału",
        placeholder="Wklej tutaj ID kanału (np. 123456789012345678)...",
        required=True
    )

    msg_title = discord.ui.TextInput(
        label="Tytuł wiadomości",
        placeholder="Nagłówek ramki (opcjonalnie)...",
        required=False
    )

    msg_content = discord.ui.TextInput(
        label="Treść wiadomości",
        style=discord.TextStyle.paragraph,
        placeholder="Wpisz treść wiadomości...",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            target_channel_id = int(self.channel_id.value.strip())
            channel = interaction.guild.get_channel(target_channel_id)

            if not channel or not isinstance(channel, discord.TextChannel):
                await interaction.response.send_message("❌ Nie znaleziono wskazanego kanału tekstowego na tym serwerze!", ephemeral=True)
                return

            embed = discord.Embed(
                title=self.msg_title.value if self.msg_title.value else None,
                description=self.msg_content.value,
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            embed.set_footer(
                text=f"Wysłano przez: {interaction.user.display_name}",
                icon_url=interaction.user.display_avatar.url
            )

            await channel.send(embed=embed)
            await interaction.response.send_message(f"✅ Wiadomość pomyślnie wysłana na kanał {channel.mention}!", ephemeral=True)

        except ValueError:
            await interaction.response.send_message("❌ Niepoprawny format ID kanału! ID musi składać się z samych cyfr.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Wystąpił błąd podczas wysyłania: {e}", ephemeral=True)

# --- WIDOKI ---

class TicketView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    
    @discord.ui.button(label="Otwórz Ticket", style=discord.ButtonStyle.primary, emoji="🎫", custom_id="persistent:open_v40")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        cat = discord.utils.get(guild.categories, name="『ETAP 1』")
        
        r_ticket = discord.utils.get(guild.roles, name="Ticket")
        r_zarzad = discord.utils.get(guild.roles, name="Zarząd")
        r_test_zarzad = discord.utils.get(guild.roles, name="Test Zarząd")
        r_szef = discord.utils.get(guild.roles, name="「 」SZEF")

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        
        roles_to_add = [r_ticket, r_zarzad, r_test_zarzad, r_szef]
        for role in roles_to_add:
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        channel = await guild.create_text_channel(f"🎫-{interaction.user.name}", category=cat, overwrites=overwrites)
        await interaction.response.send_message(f"✅ Ticket stworzony: {channel.mention}", ephemeral=True)
        await channel.send(embed=discord.Embed(title="📋 FORMULARZ", description=WZOR_PODANIA, color=0x3498db))

class VerifyView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    
    @discord.ui.button(label="Zacznij Rekrutację", style=discord.ButtonStyle.success, emoji="⚔️", custom_id="persistent:verify_v40")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = discord.utils.get(interaction.guild.roles, name="║ do rekru")
        if role: await interaction.user.add_roles(role)
        await interaction.response.send_message("✅ Nadano rangę do rekrutacji!", ephemeral=True)

class AdminDashboard(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    
    @discord.ui.select(
        placeholder="Zarządzaj gildią...",
        custom_id="persistent:admin_v40",
        options=[
            discord.SelectOption(label="BUDUJ WSZYSTKO (FULL SETUP)", value="setup", emoji="🏗️"),
            discord.SelectOption(label="Wyślij Weryfikację", value="ver", emoji="🛡️"),
            discord.SelectOption(label="Wyślij Tickety", value="tick", emoji="🎫"),
            discord.SelectOption(label="Wyślij Wiadomość na Kanał (ID)", value="send_msg", emoji="📩"),
            discord.SelectOption(label="Wyczyść czat", value="clear", emoji="🧹"),
            discord.SelectOption(label="NUKE SERVER", value="nuke", emoji="☢️")
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        guild = interaction.guild
        ev = guild.default_role

        if select.values[0] == "send_msg":
            await interaction.response.send_modal(SendEmbedModal())

        elif select.values[0] == "setup":
            await interaction.response.send_message("🚀 Buduję strukturę z uwzględnieniem Etapu 1 i Etapu 2...", ephemeral=True)
            
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
            
            p_member = {
                ev: discord.PermissionOverwrite(view_channel=False), 
                r["「 」Członek"]: discord.PermissionOverwrite(view_channel=True), 
                r["🤝 Sojusz"]: discord.PermissionOverwrite(view_channel=True), 
                r["「 」SZEF"]: discord.PermissionOverwrite(view_channel=True)
            }
            
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

            p_logs = {
                ev: discord.PermissionOverwrite(view_channel=False),
                r["Ticket"]: discord.PermissionOverwrite(view_channel=False),
                r["Test Zarząd"]: discord.PermissionOverwrite(view_channel=False),
                r["Zarząd"]: discord.PermissionOverwrite(view_channel=True),
                r["「 」SZEF"]: discord.PermissionOverwrite(view_channel=True)
            }

            c_w = await guild.create_category("・ 『Witaj/Żegnamy』 ・")
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

            c_r = await guild.create_category("・ 『Rekrutacja』 ・", overwrites=p_rekru)
            await guild.create_text_channel("🎫-ticket", category=c_r)
            await guild.create_voice_channel("🔊-Rekru 1", category=c_r, user_limit=2)
            await guild.create_voice_channel("🔊-Rekru 2", category=c_r, user_limit=2)

            await guild.create_category("『ETAP 1』", overwrites=p_rekru)
            await guild.create_category("『ETAP 2』", overwrites=p_rekru)

            c_a = await guild.create_category("・ 『Administracja』 ・", overwrites={ev: discord.PermissionOverwrite(view_channel=False)})
            await guild.create_text_channel("📑-logi", category=c_a, overwrites=p_logs)
            await guild.create_text_channel("⚙-panel", category=c_a, overwrites=p_logs)
            
            await interaction.followup.send("✅ System zbudowany pomyślnie!", ephemeral=True)

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
    
    if not keep_alive_ping.is_running():
        keep_alive_ping.start()

@bot.event
async def on_member_join(member):
    channel = discord.utils.get(member.guild.text_channels, name="💻-witamy")
    if channel:
        await channel.send(f"Witamy {member.mention} w GILDII KLON🥊")

@bot.event
async def on_member_remove(member):
    channel = discord.utils.get(member.guild.text_channels, name="💬-żegnamy")
    if channel:
        await channel.send(f"jebał cię pies śmieciu {member.mention}")

@bot.event
async def setup_hook():
    bot.add_view(AdminDashboard())
    bot.add_view(VerifyView())
    bot.add_view(TicketView())
    # Synchronizacja komend Slash (/) z serwerem Discorda
    await bot.tree.sync()
    print("✅ Zsynchronizowano komendy Slash (/)!")

# --- SLASH COMMANDS (/) ---

@bot.tree.command(name="dashboard", description="Otwiera panel sterowania botem (Tylko Admin)")
@app_commands.checks.has_permissions(administrator=True)
async def dashboard(interaction: discord.Interaction):
    await interaction.response.send_message(
        embed=discord.Embed(title="🖥️ PANEL STEROWANIA", color=0x5865F2), 
        view=AdminDashboard(),
        ephemeral=True
    )

@bot.tree.command(name="acc", description="Akceptuj ticket (przejdź do Etapu 2 lub sfinalizuj)")
async def acc(interaction: discord.Interaction):
    channel = interaction.channel
    if "🎫-" not in channel.name:
        await interaction.response.send_message("❌ Ta komenda może być używana tylko na kanałach ticketów!", ephemeral=True)
        return

    guild = interaction.guild
    current_cat = channel.category
    
    etap_1 = discord.utils.get(guild.categories, name="『ETAP 1』")
    etap_2 = discord.utils.get(guild.categories, name="『ETAP 2』")
    
    u_name = channel.name.replace("🎫-", "")
    member = discord.utils.get(guild.members, name=u_name)
    user_mention = member.mention if member else f"@{u_name}"

    # 1. JEŚLI KANAŁ JEST W ETAPIE 1 -> PRZENIEŚ DO ETAPU 2
    if etap_1 and current_cat == etap_1 and etap_2:
        await channel.edit(category=etap_2)
        
        embed_etap2 = discord.Embed(
            title="⚔️ PRZEJŚCIE DO ETAPU 2",
            description=f"{user_mention}, jak ktoś będzie miał czas, to Ci odpisze w sprawie duelu. W międzyczasie udaj się na kanał głosowy: <#1494791287533076603> lub <#1494791290569621685>",
            color=discord.Color.orange(),
            timestamp=datetime.now()
        )
        embed_etap2.set_footer(text=f"Serwer: {guild.name}")
        
        await interaction.response.send_message("✅ Przeniesiono ticket do **Etapu 2**!", ephemeral=True)
        await channel.send(embed=embed_etap2)
    
    # 2. JEŚLI KANAŁ JEST JUŻ W ETAPIE 2 -> FINALIZACJA I USUNIĘCIE TICKETU
    elif etap_2 and current_cat == etap_2:
        await interaction.response.defer(ephemeral=True)
        
        r_cz = discord.utils.get(guild.roles, name="「 」Członek")
        r_re = discord.utils.get(guild.roles, name="║ do rekru")
        if member:
            if r_cz: await member.add_roles(r_cz)
            if r_re: await member.remove_roles(r_re)

        history_messages = []
        async for message in channel.history(limit=100, oldest_first=True):
            time_str = message.created_at.strftime("%H:%M:%S")
            history_messages.append(f"**[{time_str}] {message.author.name}:** {message.content}")
        
        transcript_text = "\n".join(history_messages)
        if len(transcript_text) > 4000:
            transcript_text = transcript_text[-4000:]

        embed = discord.Embed(
            title=f"✅ Zaakceptowany Ticket: {channel.name}",
            description=transcript_text if transcript_text else "Brak wiadomości w tickecie.",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"Serwer: {guild.name}")

        try:
            await interaction.user.send(embed=embed)
        except discord.Forbidden:
            pass

        await send_log(guild, f"✅ Ticket **{channel.name}** został zaakceptowany przez {interaction.user.mention}.")
        await channel.delete()

@bot.tree.command(name="odrz", description="Odrzuć ticket i usuń kanał")
async def odrz(interaction: discord.Interaction):
    channel = interaction.channel
    if "🎫-" not in channel.name:
        await interaction.response.send_message("❌ Ta komenda może być używana tylko na kanałach ticketów!", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    u_name = channel.name.replace("🎫-", "")
    member = discord.utils.get(interaction.guild.members, name=u_name)

    history_messages = []
    async for message in channel.history(limit=100, oldest_first=True):
        time_str = message.created_at.strftime("%H:%M:%S")
        history_messages.append(f"**[{time_str}] {message.author.name}:** {message.content}")
    
    transcript_text = "\n".join(history_messages)
    if len(transcript_text) > 4000:
        transcript_text = transcript_text[-4000:]

    embed = discord.Embed(
        title=f"❌ Historia odrzuconego ticketa: {channel.name}",
        description=transcript_text if transcript_text else "Brak wiadomości w tickecie.",
        color=discord.Color.red(),
        timestamp=datetime.now()
    )
    embed.set_footer(text=f"Serwer: {interaction.guild.name}")

    if member:
        try:
            await member.send(embed=embed)
        except discord.Forbidden:
            pass

    await send_log(interaction.guild, f"❌ Ticket **{channel.name}** został odrzucony przez {interaction.user.mention}.")
    await channel.delete()

# --- NOWE KOMENDY: MODERACJA BAN & WARN ---

@bot.tree.command(name="ban", description="Zbanuj gracza z serwera")
@app_commands.checks.has_permissions(ban_members=True)
@app_commands.describe(member="Wybierz członka do zbanowania", reason="Powód zbanowania")
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "Brak powodu"):
    if member.top_role >= interaction.user.top_role and interaction.guild.owner != interaction.user:
        await interaction.response.send_message("❌ Nie możesz zbanować osoby z wyższą lub równą rangą!", ephemeral=True)
        return
    
    try:
        await member.ban(reason=f"{reason} (Zbanowany przez: {interaction.user.name})")
        
        embed = discord.Embed(
            title="🔨 ZBANOWANO GRACZA",
            description=f"**Gracz:** {member.mention} (`{member.name}`)\n**Powód:** {reason}\n**Moderator:** {interaction.user.mention}",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed)
        await send_log(interaction.guild, f"🔨 **ZBANOWANO:** {member.mention} przez {interaction.user.mention}. Powód: {reason}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Wystąpił błąd przy próbie zbanowania: {e}", ephemeral=True)

@bot.tree.command(name="warn", description="Daj ostrzeżenie (warn) graczowi")
@app_commands.checks.has_permissions(manage_messages=True)
@app_commands.describe(member="Wybierz członka do ostrzeżenia", reason="Powód ostrzeżenia")
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str = "Brak powodu"):
    embed = discord.Embed(
        title="⚠️ OSTRZEŻENIE (WARN)",
        description=f"**Użytkownik:** {member.mention}\n**Powód:** {reason}\n**Moderator:** {interaction.user.mention}",
        color=discord.Color.gold(),
        timestamp=datetime.now()
    )
    await interaction.response.send_message(embed=embed)
    
    # Powiadomienie na PW do ukaranego gracza
    try:
        await member.send(f"⚠️ Otrzymałeś ostrzeżenie na serwerze **{interaction.guild.name}**!\n**Powód:** {reason}\n**Moderator:** {interaction.user.name}")
    except discord.Forbidden:
        pass

    await send_log(interaction.guild, f"⚠️ **WARN:** {member.mention} otrzymał ostrzeżenie od {interaction.user.mention}. Powód: {reason}")

# --- OBSŁUGA BŁĘDÓW BRAKU UPRAWNIEŃ ---
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("❌ Nie posiadasz odpowiednich uprawnień do użycia tej komendy!", ephemeral=True)
    else:
        print(f"Błąd komendy Slash: {error}")

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
