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
    messages = []
    async for message in channel.history(limit=100, oldest_first=True):
        if not message.author.bot:
            messages.append(f"**{message.author.display_name}**: {message.content}")
    
    transcript_text = "\n".join(messages) if messages else "Brak treści do wyświetlenia."
    
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

async def send_log(guild, message):
    log_channel = discord.utils.get(guild.text_channels, name="📑-logi")
    if log_channel:
        embed = discord.Embed(
            title="⚙️ SYSTEM LOGS", 
            description=message, 
            color=discord.Color.dark_grey(), 
            timestamp=datetime.now()
        )
        await log_channel.send(embed=embed)

def has_management_permission(member: discord.Member) -> bool:
    if member == member.guild.owner or member.guild_permissions.administrator:
        return True
    allowed_keywords = ["szef", "zarząd", "rekruter"]
    for role in member.roles:
        if any(keyword in role.name.lower() for keyword in allowed_keywords):
            return True
    return False

@tasks.loop(minutes=10)
async def keep_alive_ping():
    url = os.environ.get("RENDER_EXTERNAL_URL")
    if url:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    print(f"⏰ [KEEP-ALIVE] Ping wysłany do {url} | Status: {response.status}")
        except Exception as e:
            print(f"⚠️ [KEEP-ALIVE] Błąd: {e}")

def get_ticket_target(channel: discord.TextChannel, moderator: discord.Member):
    target = None
    for obj, overwrite in channel.overwrites.items():
        if isinstance(obj, discord.Member) and not obj.bot and obj != moderator:
            target = obj
            break
    return target

# --- FORMULARZ PODANIA ---

class PodanieModal(discord.ui.Modal, title="📝 Formularz Podania"):
    q1 = discord.ui.TextInput(label="1. Nick z Minecrafta", placeholder="Twój nick...", style=discord.TextStyle.short, required=True, max_length=32)
    q2 = discord.ui.TextInput(label="2. Ile masz lat?", placeholder="Twój wiek...", style=discord.TextStyle.short, required=True, max_length=10)
    q9 = discord.ui.TextInput(label="9. Podaj 3 ostatnie gildie", placeholder="Gildie...", style=discord.TextStyle.paragraph, required=True, max_length=200)
    q10 = discord.ui.TextInput(label="10. Dlaczego my?", placeholder="Powód...", style=discord.TextStyle.paragraph, required=True, max_length=300)
    q13 = discord.ui.TextInput(label="13. Czy znasz kogoś?", placeholder="Znajomi...", style=discord.TextStyle.short, required=True, max_length=100)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.user.edit(nick=self.q1.value.strip())
        except Exception:
            pass

        embed = discord.Embed(
            title=f"📋 PODANIE REKRUTACYJNE — {interaction.user.display_name}",
            description=f"**Kandydat:** {interaction.user.mention}\n**Data:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name="➞ 1. Nick z Minecrafta »", value=self.q1.value, inline=False)
        embed.add_field(name="➞ 2. Ile masz lat? »", value=self.q2.value, inline=False)
        embed.add_field(name="➞ 9. Podaj 3 ostatnie gildie »", value=self.q9.value, inline=False)
        embed.add_field(name="➞ 10. Dlaczego my? »", value=self.q10.value, inline=False)
        embed.add_field(name="➞ 13. Czy znasz kogoś? »", value=self.q13.value, inline=False)

        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("✅ Podanie zostało wysłane!", ephemeral=True)
        await send_log(interaction.guild, f"📝 **NOWE PODANIE:** Użytkownik {interaction.user.mention} wypełnił podanie.")

class SendEmbedModal(discord.ui.Modal, title="📩 Wyślij wiadomość w ramce"):
    channel_id = discord.ui.TextInput(label="ID Kanału", placeholder="Wklej ID kanału...", required=True)
    msg_title = discord.ui.TextInput(label="Tytuł wiadomości", placeholder="Nagłówek...", required=False)
    msg_content = discord.ui.TextInput(label="Treść wiadomości", style=discord.TextStyle.paragraph, placeholder="Treść...", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            target_channel_id = int(self.channel_id.value.strip())
            channel = interaction.guild.get_channel(target_channel_id)
            if not channel or not isinstance(channel, discord.TextChannel):
                await interaction.response.send_message("❌ Nie znaleziono kanału!", ephemeral=True)
                return

            embed = discord.Embed(
                title=self.msg_title.value if self.msg_title.value else None,
                description=self.msg_content.value,
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            embed.set_footer(text=f"Wysłano przez: {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
            await channel.send(embed=embed)
            await interaction.response.send_message(f"✅ Wiadomość wysłana na {channel.mention}!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Błąd: {e}", ephemeral=True)

class PodanieTicketView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="Napisz podanie", style=discord.ButtonStyle.success, emoji="📝", custom_id="persistent:fill_podanie_single")
    async def fill_podanie(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PodanieModal())

class KlepaView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.wchodza = []
        self.pozniej = []
        self.nie_moga = []

    @discord.ui.button(label="🟢 Wchodzę (0)", style=discord.ButtonStyle.success, custom_id="klepa_v1:wchodze")
    async def wchodze(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user.mention
        if user in self.pozniej: self.pozniej.remove(user)
        if user in self.nie_moga: self.nie_moga.remove(user)
        if user not in self.wchodza: self.wchodza.append(user)
        await self.update_msg(interaction)

    @discord.ui.button(label="🟡 Będę później (0)", style=discord.ButtonStyle.secondary, custom_id="klepa_v1:pozniej")
    async def pozniej(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user.mention
        if user in self.wchodza: self.wchodza.remove(user)
        if user in self.nie_moga: self.nie_moga.remove(user)
        if user not in self.pozniej: self.pozniej.append(user)
        await self.update_msg(interaction)

    @discord.ui.button(label="🔴 Nie mogę (0)", style=discord.ButtonStyle.danger, custom_id="klepa_v1:niemoge")
    async def niemoge(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user.mention
        if user in self.wchodza: self.wchodza.remove(user)
        if user in self.pozniej: self.pozniej.remove(user)
        if user not in self.nie_moga: self.nie_moga.append(user)
        await self.update_msg(interaction)

    async def update_msg(self, interaction: discord.Interaction):
        self.children[0].label = f"🟢 Wchodzę ({len(self.wchodza)})"
        self.children[1].label = f"🟡 Będę później ({len(self.pozniej)})"
        self.children[2].label = f"🔴 Nie mogę ({len(self.nie_moga)})"
        
        embed = interaction.message.embeds[0]
        embed.set_field_at(0, name="🟢 Wchodzą:", value=", ".join(self.wchodza) if self.wchodza else "Brak", inline=False)
        embed.set_field_at(1, name="🟡 Będą później:", value=", ".join(self.pozniej) if self.pozniej else "Brak", inline=False)
        embed.set_field_at(2, name="🔴 Nie mogą:", value=", ".join(self.nie_moga) if self.nie_moga else "Brak", inline=False)
        await interaction.response.edit_message(embed=embed, view=self)

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
        
        for role in [r_ticket, r_zarzad, r_test_zarzad, r_szef]:
            if role: overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        channel = await guild.create_text_channel(f"🎫-{interaction.user.name}", category=cat, overwrites=overwrites)
        await interaction.response.send_message(f"✅ Ticket stworzony: {channel.mention}", ephemeral=True)
        
        embed_podanie = discord.Embed(
            title="📋 FORMULARZ REKRUTACYJNY",
            description="Kliknij poniższy przycisk **📝 Napisz podanie**, aby otworzyć formularz rekrutacyjny.",
            color=0x3498db
        )
        await channel.send(embed=embed_podanie, view=PodanieTicketView())

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
            return

        await interaction.response.defer(ephemeral=True)

        if select.values[0] == "setup":
            roles_data = {
                "「 」SZEF": 0x992d22, "Zarząd": 0x740909, "Test Zarząd": 0xe67e22, 
                "Rekruter": 0x3498db, "Ticket": 0x00ffff, "「 」Członek": 0x9b59b6, 
                "🤝 Sojusz": 0xf1c40f, "║ do rekru": 0x2ecc71
            }
            r = {}
            for n, c in roles_data.items():
                role = discord.utils.get(guild.roles, name=n) or await guild.create_role(name=n, color=discord.Color(c), hoist=True)
                r[n] = role
            
            p_member = {ev: discord.PermissionOverwrite(view_channel=False), r["「 」Członek"]: discord.PermissionOverwrite(view_channel=True), r["🤝 Sojusz"]: discord.PermissionOverwrite(view_channel=True), r["「 」SZEF"]: discord.PermissionOverwrite(view_channel=True)}
            p_rekru = {ev: discord.PermissionOverwrite(view_channel=False), r["「 」Członek"]: discord.PermissionOverwrite(view_channel=False), r["Ticket"]: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True), r["Rekruter"]: discord.PermissionOverwrite(view_channel=True), r["Test Zarząd"]: discord.PermissionOverwrite(view_channel=True), r["Zarząd"]: discord.PermissionOverwrite(view_channel=True), r["「 」SZEF"]: discord.PermissionOverwrite(view_channel=True), r["║ do rekru"]: discord.PermissionOverwrite(view_channel=True)}
            p_logs = {ev: discord.PermissionOverwrite(view_channel=False), r["Ticket"]: discord.PermissionOverwrite(view_channel=False), r["Test Zarząd"]: discord.PermissionOverwrite(view_channel=False), r["Zarząd"]: discord.PermissionOverwrite(view_channel=True), r["「 」SZEF"]: discord.PermissionOverwrite(view_channel=True)}

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
            await interaction.followup.send("✅ System zbudowany!", ephemeral=True)

        elif select.values[0] == "ver": 
            await interaction.channel.send(embed=discord.Embed(title="🛡️ WERYFIKACJA", color=0x2ecc71), view=VerifyView())
            await interaction.followup.send("✅ Wysłano panel weryfikacji!", ephemeral=True)
        elif select.values[0] == "tick": 
            await interaction.channel.send(embed=discord.Embed(title="🎫 REKRUTACJA", color=0x3498db), view=TicketView())
            await interaction.followup.send("✅ Wysłano panel ticketów!", ephemeral=True)
        elif select.values[0] == "clear": 
            await interaction.channel.purge(limit=100)
            await interaction.followup.send("✅ Wyczyśćono czat!", ephemeral=True)
        elif select.values[0] == "nuke":
            if interaction.user == guild.owner:
                for c in guild.channels: await c.delete()
                await guild.create_text_channel("nuke-done")
            else:
                await interaction.followup.send("❌ Tylko właściciel serwera może użyć NUKE!", ephemeral=True)

# --- BOT EVENTS & SYNCHRONIZACJA ---

@bot.event
async def on_ready():
    global bot_status
    bot_status = f"Zalogowany jako {bot.user}"
    print(f"✅ Bot online: {bot.user}")
    if not keep_alive_ping.is_running(): 
        keep_alive_ping.start()

@bot.event
async def setup_hook():
    bot.add_view(AdminDashboard())
    bot.add_view(VerifyView())
    bot.add_view(TicketView())
    bot.add_view(KlepaView())
    bot.add_view(PodanieTicketView())
    
    await bot.tree.sync()
    print("⚡ Zsynchronizowano komendy globalnie!")

@bot.command(name="sync")
@commands.has_permissions(administrator=True)
async def sync_prefix(ctx):
    synced = await bot.tree.sync()
    await ctx.send(f"✅ Zsynchronizowano {len(synced)} komend `/`!")

# --- KOMENDY SLASH ---

@bot.tree.command(name="dashboard", description="Otwiera panel zarządczy bota")
@app_commands.checks.has_permissions(administrator=True)
async def dashboard(interaction: discord.Interaction):
    embed = discord.Embed(
        title="⚙️ PANEL ZARZĄDZANIA GILDIA",
        description="Wybierz opcję z poniższego menu rozwijanego.",
        color=discord.Color.gold()
    )
    await interaction.response.send_message(embed=embed, view=AdminDashboard(), ephemeral=True)

@bot.tree.command(name="acc", description="Akceptuje podanie (1. wpisanie przenosi do Etapu 2, 2. wpisanie finalizuje i wysyła historię)")
async def acc(interaction: discord.Interaction):
    if not has_management_permission(interaction.user):
        await interaction.response.send_message("❌ Brak uprawnień!", ephemeral=True)
        return

    target = get_ticket_target(interaction.channel, interaction.user)
    if not target:
        await interaction.response.send_message("❌ Nie znaleziono kandydata na tym kanale!", ephemeral=True)
        return

    is_in_etap2 = interaction.channel.category and interaction.channel.category.name == "『ETAP 2』"

    if not is_in_etap2:
        # PIERWSZE /ACC - Przeniesienie do Etapu 2 z oryginalnym napisem
        etap2_cat = discord.utils.get(interaction.guild.categories, name="『ETAP 2』")
        if etap2_cat:
            try:
                await interaction.channel.edit(category=etap2_cat)
            except Exception:
                pass

        embed = discord.Embed(
            title="🎉 PODANIE ZAAKCEPTOWANE!",
            description=f"Kandydat {target.mention} pomyślnie przeszedł rekrutację i został **PRZYJĘTY** do gildii przez {interaction.user.mention}!",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed)
        await send_log(interaction.guild, f"🔄 **ETAP 2:** Kandydat {target.mention} przeniesiony do Etapu 2 przez {interaction.user.mention}.")
    else:
        # DRUGIE /ACC - Finał rekrutacji, nadanie rangi i wysłanie historii na DM
        r_czlonek = discord.utils.get(interaction.guild.roles, name="「 」Członek")
        r_do_rekru = discord.utils.get(interaction.guild.roles, name="║ do rekru")
        r_ticket = discord.utils.get(interaction.guild.roles, name="Ticket")

        if r_czlonek: await target.add_roles(r_czlonek)
        if r_do_rekru and r_do_rekru in target.roles: await target.remove_roles(r_do_rekru)
        if r_ticket and r_ticket in target.roles: await target.remove_roles(r_ticket)

        success = await send_transcript_dm(interaction.user, interaction.channel)

        embed = discord.Embed(
            title="🎉 PODANIE ZAAKCEPTOWANE (FINAŁ)!",
            description=f"Kandydat {target.mention} został w pełni zatwierdzony i ukończył rekrutację przez {interaction.user.mention}!",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        if not success:
            embed.add_field(name="⚠️ Uwaga:", value="Nie udało się wysłać transkryptu na Twój DM (masz zablokowane wiadomości prywatne).")

        await interaction.response.send_message(embed=embed)
        await send_log(interaction.guild, f"✅ **AKCEPTACJA KOŃCOWA:** Użytkownik {target.mention} przyjęty przez {interaction.user.mention}. Historia wysłana na DM.")

@bot.tree.command(name="odrz", description="Odrzuca kandydata z ticketa i przesyła historię na jego DM")
async def odrz(interaction: discord.Interaction):
    if not has_management_permission(interaction.user):
        await interaction.response.send_message("❌ Brak uprawnień!", ephemeral=True)
        return

    target = get_ticket_target(interaction.channel, interaction.user)
    if not target:
        await interaction.response.send_message("❌ Nie znaleziono kandydata na tym kanale!", ephemeral=True)
        return

    r_do_rekru = discord.utils.get(interaction.guild.roles, name="║ do rekru")
    r_ticket = discord.utils.get(interaction.guild.roles, name="Ticket")
    if r_do_rekru and r_do_rekru in target.roles: await target.remove_roles(r_do_rekru)
    if r_ticket and r_ticket in target.roles: await target.remove_roles(r_ticket)

    success = await send_transcript_dm(target, interaction.channel)

    embed = discord.Embed(
        title="❌ PODANIE ODRZUCONE",
        description=f"Podanie gracza {target.mention} zostało **ODRZUCONE** przez {interaction.user.mention}.",
        color=discord.Color.red(),
        timestamp=datetime.now()
    )
    if not success:
        embed.add_field(name="⚠️ Uwaga:", value="Nie udało się wysłać transkryptu na DM gracza (ma zablokowane wiadomości prywatne).")

    await interaction.response.send_message(embed=embed)
    await send_log(interaction.guild, f"❌ **ODRZUCENIE:** Kandydat {target.mention} odrzucony przez {interaction.user.mention}.")

@bot.tree.command(name="zamknij", description="Zamyka i usuwa obecny ticket")
async def zamknij(interaction: discord.Interaction):
    if not has_management_permission(interaction.user):
        await interaction.response.send_message("❌ Brak uprawnień!", ephemeral=True)
        return
        
    if not interaction.channel.name.startswith("🎫-"):
        await interaction.response.send_message("❌ Ta komenda działa tylko na kanałach ticketów!", ephemeral=True)
        return
        
    await interaction.response.send_message("🔒 **Ticket zostanie usunięty za 5 sekund...**")
    await asyncio.sleep(5)
    await interaction.channel.delete()

@bot.tree.command(name="klepa", description="Wysyła ogłoszenie mobilizacji na klepę")
async def klepa(interaction: discord.Interaction, opis: str = "Przebijają nas, wbijajcie!"):
    embed = discord.Embed(title="🚨 MOBILIZACJA 🚨", description=opis, color=discord.Color.red())
    embed.add_field(name="🟢 Wchodzą:", value="Brak", inline=False)
    embed.add_field(name="🟡 Będą później:", value="Brak", inline=False)
    embed.add_field(name="🔴 Nie mogą:", value="Brak", inline=False)
    await interaction.channel.send(content="@everyone przebijają nas!", embed=embed, view=KlepaView())
    await interaction.response.send_message("Wysłano!", ephemeral=True)

@bot.tree.command(name="nick", description="Zmienia Twój nick na serwerze")
async def nick(interaction: discord.Interaction, nick_mc: str):
    try:
        await interaction.user.edit(nick=nick_mc)
        await interaction.response.send_message(f"Zmieniono nick na: {nick_mc}", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Błąd zmiany nicku: {e}", ephemeral=True)

@bot.event
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ Nie masz uprawnień!", ephemeral=True)
    else:
        print(f"⚠️ Błąd komendy slash: {error}")

if __name__ == "__main__":
    TOKEN = os.environ.get("DISCORD_TOKEN")
    if not TOKEN:
        print("❌ BŁĄD: Brak DISCORD_TOKEN!")
        exit(1)

    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
    bot.run(TOKEN)
