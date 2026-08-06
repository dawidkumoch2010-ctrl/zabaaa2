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

# Słownik tymczasowy na postępy formularza (17 pytań w 4 etapach)
user_applications = {}

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

# --- MECHANIZM KEEP-ALIVE (PING CO 10 MINUT) ---
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

# --- MODALE (FORMULARZE) ---

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

# --- ETAP 1 (Pytania 1 - 5) ---
class PodanieEtap1Modal(discord.ui.Modal, title="📝 Rekrutacja - Etap 1/4"):
    q1 = discord.ui.TextInput(label="1. Nick z Minecrafta", style=discord.TextStyle.short, placeholder="Twój dokładny nick w grze...", required=True, max_length=32)
    q2 = discord.ui.TextInput(label="2. Ile masz lat?", style=discord.TextStyle.short, placeholder="np. 16", required=True, max_length=10)
    q3 = discord.ui.TextInput(label="3. Dzienna aktywność", style=discord.TextStyle.short, placeholder="np. 3-5h dziennie", required=True, max_length=50)
    q4 = discord.ui.TextInput(label="4. Od kiedy grasz gildie", style=discord.TextStyle.short, placeholder="np. od 2 lat / od 2021 roku", required=True, max_length=100)
    q5 = discord.ui.TextInput(label="5. Twoje PvP od 1 do 10", style=discord.TextStyle.short, placeholder="np. 8/10", required=True, max_length=10)

    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        user_applications[user_id] = {
            "q1": self.q1.value.strip(),
            "q2": self.q2.value.strip(),
            "q3": self.q3.value.strip(),
            "q4": self.q4.value.strip(),
            "q5": self.q5.value.strip(),
        }
        await interaction.response.send_message(
            "✅ **Etap 1/4 ukończony!** Kliknij poniższy przycisk, aby przejść do **Etapu 2** (Pytania 6-10).",
            view=Etap2View(),
            ephemeral=True
        )

class Etap2View(discord.ui.View):
    def __init__(self): super().__init__(timeout=300)

    @discord.ui.button(label="Przejdź do Etapu 2 (Pytania 6-10)", style=discord.ButtonStyle.primary, emoji="➡️")
    async def next_etap(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PodanieEtap2Modal())

# --- ETAP 2 (Pytania 6 - 10) ---
class PodanieEtap2Modal(discord.ui.Modal, title="📝 Rekrutacja - Etap 2/4"):
    q6 = discord.ui.TextInput(label="6. Co robisz gdy zginiesz na przebicie?", style=discord.TextStyle.paragraph, placeholder="Opisz swoje zachowanie...", required=True, max_length=200)
    q7 = discord.ui.TextInput(label="7. Kiedy kończysz edycję?", style=discord.TextStyle.short, placeholder="np. gram do końca edycji", required=True, max_length=100)
    q8 = discord.ui.TextInput(label="8. Czy drzesz mordę na klepie?", style=discord.TextStyle.short, placeholder="np. Nie, zachowuję spokój", required=True, max_length=100)
    q9 = discord.ui.TextInput(label="9. Podaj 3 ostatnie gildie", style=discord.TextStyle.paragraph, placeholder="Wpisz nazwy 3 ostatnich gildii...", required=True, max_length=200)
    q10 = discord.ui.TextInput(label="10. Dlaczego my?", style=discord.TextStyle.paragraph, placeholder="Napisz dlaczego wybranieś naszą gildie...", required=True, max_length=300)

    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        if user_id in user_applications:
            user_applications[user_id].update({
                "q6": self.q6.value.strip(),
                "q7": self.q7.value.strip(),
                "q8": self.q8.value.strip(),
                "q9": self.q9.value.strip(),
                "q10": self.q10.value.strip(),
            })
            await interaction.response.send_message(
                "✅ **Etap 2/4 ukończony!** Kliknij poniższy przycisk, aby przejść do **Etapu 3** (Pytania 11-15).",
                view=Etap3View(),
                ephemeral=True
            )
        else:
            await interaction.response.send_message("❌ Sesja wygasła. Kliknij przycisk i zacznij od nowa.", ephemeral=True)

class Etap3View(discord.ui.View):
    def __init__(self): super().__init__(timeout=300)

    @discord.ui.button(label="Przejdź do Etapu 3 (Pytania 11-15)", style=discord.ButtonStyle.primary, emoji="➡️")
    async def next_etap(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PodanieEtap3Modal())

# --- ETAP 3 (Pytania 11 - 15) ---
class PodanieEtap3Modal(discord.ui.Modal, title="📝 Rekrutacja - Etap 3/4"):
    q11 = discord.ui.TextInput(label="11. Skille (slime/water)", style=discord.TextStyle.short, placeholder="np. Slime 8/10, Water 9/10", required=True, max_length=100)
    q12 = discord.ui.TextInput(label="12. Staty (Mogą być SS)", style=discord.TextStyle.short, placeholder="Opisz staty (screena możesz dać na czat)", required=True, max_length=150)
    q13 = discord.ui.TextInput(label="13. Słuchasz liderówki?", style=discord.TextStyle.short, placeholder="np. Tak", required=True, max_length=50)
    q14 = discord.ui.TextInput(label="14. Znasz kogoś?", style=discord.TextStyle.short, placeholder="Wpisz kogo znasz z ekipy...", required=True, max_length=100)
    q15 = discord.ui.TextInput(label="15. Na ile zostajesz?", style=discord.TextStyle.short, placeholder="np. Na całą edycję", required=True, max_length=100)

    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        if user_id in user_applications:
            user_applications[user_id].update({
                "q11": self.q11.value.strip(),
                "q12": self.q12.value.strip(),
                "q13": self.q13.value.strip(),
                "q14": self.q14.value.strip(),
                "q15": self.q15.value.strip(),
            })
            await interaction.response.send_message(
                "✅ **Etap 3/4 ukończony!** Kliknij poniższy przycisk, aby przejść do ostatniego **Etapu 4** (Pytania 16-17).",
                view=Etap4View(),
                ephemeral=True
            )
        else:
            await interaction.response.send_message("❌ Sesja wygasła. Zacznij od nowa.", ephemeral=True)

class Etap4View(discord.ui.View):
    def __init__(self): super().__init__(timeout=300)

    @discord.ui.button(label="Przejdź do Etapu 4 (Pytania 16-17)", style=discord.ButtonStyle.success, emoji="✅")
    async def next_etap(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PodanieEtap4Modal())

# --- ETAP 4 (Pytania 16 - 17) & FINAŁ ---
class PodanieEtap4Modal(discord.ui.Modal, title="📝 Rekrutacja - Etap 4/4"):
    q16 = discord.ui.TextInput(label="16. Doświadczenie 1.16", style=discord.TextStyle.paragraph, placeholder="Opisz swoje opanowanie wersji 1.16...", required=True, max_length=200)
    q17 = discord.ui.TextInput(label="17. Toksyczność / Dystans", style=discord.TextStyle.paragraph, placeholder="Napisz czy masz dystans do siebie...", required=True, max_length=200)

    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        if user_id not in user_applications:
            await interaction.response.send_message("❌ Sesja wygasła. Wypełnij podanie od nowa.", ephemeral=True)
            return

        data = user_applications[user_id]
        data["q16"] = self.q16.value.strip()
        data["q17"] = self.q17.value.strip()

        mc_nickname = data["q1"]
        nickname_changed = False

        try:
            await interaction.user.edit(nick=mc_nickname)
            nickname_changed = True
        except discord.Forbidden:
            nickname_changed = False
        except Exception as e:
            print(f"Błąd przy zmianie nicku: {e}")

        embed = discord.Embed(
            title=f"📋 WYPEŁNIONE PODANIE — {interaction.user.display_name}",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"Złożono przez: {interaction.user.name}", icon_url=interaction.user.display_avatar.url)

        embed.add_field(name="🎮 1. Nick Minecraft", value=f"`{mc_nickname}`" + (" *(Automatycznie zmieniono nick ✅)*" if nickname_changed else ""), inline=False)
        embed.add_field(name="🎂 2. Ile masz lat?", value=data["q2"], inline=True)
        embed.add_field(name="⏰ 3. Dzienna aktywność", value=data["q3"], inline=True)
        embed.add_field(name="📜 4. Od kiedy grasz gildie", value=data["q4"], inline=False)
        embed.add_field(name="⚔️ 5. Twoje PvP (1-10)", value=data["q5"], inline=True)
        embed.add_field(name="💥 6. Zgon na przebicie", value=data["q6"], inline=False)
        embed.add_field(name="🏁 7. Kiedy kończysz edycję?", value=data["q7"], inline=True)
        embed.add_field(name="🗣️ 8. Czy drzesz mordę na klepie?", value=data["q8"], inline=True)
        embed.add_field(name="🛡️ 9. Podaj 3 ostatnie gildie", value=data["q9"], inline=False)
        embed.add_field(name="💡 10. Dlaczego my?", value=data["q10"], inline=False)
        embed.add_field(name="🎯 11. Skille (slime/water)", value=data["q11"], inline=True)
        embed.add_field(name="📊 12. Staty", value=data["q12"], inline=True)
        embed.add_field(name="👑 13. Słuchasz liderówki?", value=data["q13"], inline=True)
        embed.add_field(name="👥 14. Znasz kogoś?", value=data["q14"], inline=True)
        embed.add_field(name="⏳ 15. Na ile zostajesz?", value=data["q15"], inline=True)
        embed.add_field(name="🧱 16. Doświadczenie 1.16", value=data["q16"], inline=False)
        embed.add_field(name="🎭 17. Toksyczność / Dystans", value=data["q17"], inline=False)

        await interaction.channel.send(embed=embed)

        del user_applications[user_id]

        msg = "🎉 **Podanie zostało pomyślnie wysłane!**"
        if nickname_changed:
            msg += f"\n✏️ Twój nick został zmieniono na **{mc_nickname}**."
        else:
            msg += f"\n⚠️ Nie udało się zmienić nicku (brak uprawnień bota)."

        await interaction.response.send_message(msg, ephemeral=True)
        await send_log(interaction.guild, f"📝 **NOWE PODANIE:** Użytkownik {interaction.user.mention} wypełnił podanie (Nick: **{mc_nickname}**).")

# --- WIDOKI ---

class PodanieTicketView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="Wypełnij podanie", style=discord.ButtonStyle.success, emoji="📝", custom_id="persistent:fill_podanie_v1")
    async def fill_podanie(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PodanieEtap1Modal())

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
        
        roles_to_add = [r_ticket, r_zarzad, r_test_zarzad, r_szef]
        for role in roles_to_add:
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        channel = await guild.create_text_channel(f"🎫-{interaction.user.name}", category=cat, overwrites=overwrites)
        await interaction.response.send_message(f"✅ Ticket stworzony: {channel.mention}", ephemeral=True)
        
        embed_podanie = discord.Embed(
            title="📋 FORMULARZ REKRUTACYJNY",
            description="Kliknij poniższy przycisk **📝 Wypełnij podanie**, aby otworzyć okienko rekrutacyjne i odpowiedzieć na pytania!",
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

# --- BOT EVENTS ---

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
    synced = await bot.tree.sync()
    print(f"✅ Zsynchronizowano komendy Slash ({len(synced)} komend)")

# --- KOMENDY SLASH (APP COMMANDS) ---

@bot.tree.command(name="dashboard", description="Otwiera panel zarządczy bota (Tylko dla Administratorów)")
@app_commands.checks.has_permissions(administrator=True)
async def dashboard(interaction: discord.Interaction):
    embed = discord.Embed(
        title="⚙️ PANEL ZARZĄDZANIA GILDIA",
        description="Wybierz opcję z poniższego menu rozwijanego, aby wykonać akcję.",
        color=discord.Color.gold()
    )
    await interaction.response.send_message(embed=embed, view=AdminDashboard(), ephemeral=True)

@bot.tree.command(name="acc", description="Akceptuje podanie gracza (W Etapie 1 przenosi do Etapu 2, w Etapie 2 przyznaje rangę)")
@app_commands.checks.has_permissions(manage_roles=True)
async def acc(interaction: discord.Interaction, uzytkownik: discord.Member = None):
    target = uzytkownik
    if not target:
        for member in interaction.channel.members:
            if not member.bot and member != interaction.user:
                target = member
                break

    if not target:
        await interaction.response.send_message("❌ Nie znaleziono użytkownika! Użyj `/acc @użytkownik`.", ephemeral=True)
        return

    current_category = interaction.channel.category.name if (interaction.channel and interaction.channel.category) else ""

    # --- ETAP 1 -> PRZENIESIENIE DO ETAPU 2 ---
    if current_category == "『ETAP 1』":
        etap2_cat = discord.utils.get(interaction.guild.categories, name="『ETAP 2』")
        if etap2_cat:
            await interaction.channel.edit(category=etap2_cat)

        embed = discord.Embed(
            title="🟡 ETAP 1 ZDAJĄCY — PRZEJŚCIE DO ETAPU 2",
            description=f"Kandydat {target.mention} zdał **Etap 1** (pisemny)!\n\n📌 **Ticket został przeniesiony do kategorii `『ETAP 2』`**. Oczekuj na rozmowę głosową / dalszą sprawdziankę.",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed)
        await send_log(interaction.guild, f"➡️ **ETAP 1 ZDAJĄCY:** Użytkownik {target.mention} został przeniesiony do Etapu 2 przez {interaction.user.mention}.")

    # --- ETAP 2 -> PEŁNA AKCEPTACJA I NADANIE RANGI ---
    else:
        r_czlonek = discord.utils.get(interaction.guild.roles, name="「 」Członek")
        r_do_rekru = discord.utils.get(interaction.guild.roles, name="║ do rekru")
        r_ticket = discord.utils.get(interaction.guild.roles, name="Ticket")

        if r_czlonek:
            await target.add_roles(r_czlonek)
        if r_do_rekru and r_do_rekru in target.roles:
            await target.remove_roles(r_do_rekru)
        if r_ticket and r_ticket in target.roles:
            await target.remove_roles(r_ticket)

        embed = discord.Embed(
            title="🎉 PODANIE I REKRUTACJA ZAAKCEPTOWANA!",
            description=f"Kandydat {target.mention} pomyślnie przeszedł **Etap 2** i został oficjalnie **PRZYJĘTY** do gildii przez {interaction.user.mention}!",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed)
        await send_log(interaction.guild, f"✅ **PEŁNA AKCEPTACJA:** Użytkownik {target.mention} został przyjęty do gildii przez {interaction.user.mention}.")

        # Zamknięcie kanału ticket po 5 sekundach
        await asyncio.sleep(5)
        if interaction.channel.name.startswith("🎫-"):
            await interaction.channel.delete()

@bot.tree.command(name="odrz", description="Odrzuca podanie użytkownika i zamyka ticket")
@app_commands.checks.has_permissions(manage_roles=True)
async def odrz(interaction: discord.Interaction, uzytkownik: discord.Member = None, powod: str = "Brak podanego powodu"):
    target = uzytkownik
    if not target:
        for member in interaction.channel.members:
            if not member.bot and member != interaction.user:
                target = member
                break

    if not target:
        await interaction.response.send_message("❌ Nie znaleziono użytkownika! Użyj `/odrz @użytkownik`.", ephemeral=True)
        return

    r_do_rekru = discord.utils.get(interaction.guild.roles, name="║ do rekru")
    r_ticket = discord.utils.get(interaction.guild.roles, name="Ticket")

    if r_do_rekru and r_do_rekru in target.roles:
        await target.remove_roles(r_do_rekru)
    if r_ticket and r_ticket in target.roles:
        await target.remove_roles(r_ticket)

    embed = discord.Embed(
        title="❌ PODANIE ODRZUCONE",
        description=f"Podanie gracza {target.mention} zostało **ODRZUCONE** przez {interaction.user.mention}.\n**Powód:** {powod}",
        color=discord.Color.red(),
        timestamp=datetime.now()
    )
    await interaction.response.send_message(embed=embed)
    await send_log(interaction.guild, f"❌ **ODRZUCENIE:** Podanie {target.mention} odrzucone przez {interaction.user.mention}. Powód: {powod}")

    # Zamknięcie kanału ticket po 5 sekundach
    await asyncio.sleep(5)
    if interaction.channel.name.startswith("🎫-"):
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

# --- OBSŁUGA BŁĘDÓW UPRAWNIEŃ ---

@bot.event
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ Nie masz wystarczających uprawnień do użycia tej komendy!", ephemeral=True)
    else:
        print(f"⚠️ Błąd komendy slash: {error}")

# --- URUCHAMIANIE ---

if __name__ == "__main__":
    TOKEN = os.environ.get("DISCORD_TOKEN")
    if not TOKEN:
        print("❌ BŁĄD: Upewnij się, że dodałeś zmienną środowiskową DISCORD_TOKEN w panelu Render!")
        exit(1)

    # Uruchomienie serwera WWW Flask w osobnym wątku
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()

    # Uruchomienie bota Discorda
    bot.run(TOKEN)
