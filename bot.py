import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime
import pytz
import json
import random

# Read token from environment variable; raise error if missing
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN environment variable not set")

INTENTS = discord.Intents.default()
INTENTS.message_content = True

bot = commands.Bot(command_prefix="!", intents=INTENTS)
COLOR = 0x393A41
ALLOWED_USER_ID = 818502458640564224
GUILD_ID = 1382085308908179668
PROMO_CHANNEL_ID = 1474152287310970973

PROMO_DATA_FILE = "promo_data.json"
PROJECTS_FILE = "projects.json"
TICKET_DATA_FILE = "ticket_data.json"

PROMO_DATE = datetime.date(2026, 2, 23)

GIF_URLS = [
    "https://media.discordapp.net/attachments/1456759165358706739/1474153567483990173/23_.gif?ex=6998cffe&is=69977e7e&hm=78417cf3d0c767d09e15cc2871f4066b958087e1500f0e51c7601076b3f7c907&=&width=522&height=293",
]

# ───────────────────────────────────────────────
#  Утилиты загрузки/сохранения файлов
# ───────────────────────────────────────────────

def load_promo_data():
    if os.path.exists(PROMO_DATA_FILE):
        with open(PROMO_DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"last_gif_id": None, "last_message_id": None, "sent": False}

def save_promo_data(data):
    with open(PROMO_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_projects():
    if os.path.exists(PROJECTS_FILE):
        with open(PROJECTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_projects(data):
    with open(PROJECTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_ticket_data():
    if os.path.exists(TICKET_DATA_FILE):
        with open(TICKET_DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_ticket_data(data):
    with open(TICKET_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ───────────────────────────────────────────────
#  Построитель эмбеда акции
# ───────────────────────────────────────────────

def build_promo_embed(footer_text: str) -> discord.Embed:
    embed = discord.Embed(
        title="<:Vector:1446872238266519582> ㅤ — ㅤ 23 февраля",
        color=COLOR
    )
    embed.add_field(
        name="ㅤ🎯ㅤ Боевой пакет",
        value=(
            "ㅤ\\n"
            "GUI + HUD — два элемента, которые всегда берут вместе. "
            "23 февраля объединяем их в один боевой комплект со скидкой **20%**. "
            "Никаких условий — просто берёшь оба и платишь меньше. "
            "Один день, один пакет, одна цена.\\n"
            "ㅤ"
        ),
        inline=False
    )
    embed.add_field(
        name="ㅤ🎖️ㅤ Приказ №23",
        value=(
            "ㅤ\\n"
            "Специальный приказ для тех, кто заслужил статус <@&1418353852234600508>. "
            "23 февраля — скидка **23%** на абсолютно любую услугу без исключений и ограничений. "
            "Никаких условий, никакого минимального чека — просто ваша привилегия за верность проекту. "
            "Действует строго один день.\\n"
            "ㅤ"
        ),
        inline=False
    )
    embed.set_footer(text=footer_text)
    return embed

# ───────────────────────────────────────────────
#  Тикет-мониторинг
# ───────────────────────────────────────────────

@bot.event
async def on_message(message):
    if message.author.bot:
        await bot.process_commands(message)
        return

    await bot.process_commands(message)

    if "ticket-" not in message.channel.name.lower():
        return

    ticket_data = load_ticket_data()
    channel_id = str(message.channel.id)

    if message.author.id == ALLOWED_USER_ID:
        # Админ ответил — сбрасываем отслеживание
        ticket_data[channel_id] = {
            "last_non_admin_ts": None,
            "pinged": False
        }
    else:
        # Новое сообщение не от админа — обновляем время, сбрасываем пинг
        ticket_data[channel_id] = {
            "last_non_admin_ts": message.created_at.isoformat(),
            "pinged": False
        }

    save_ticket_data(ticket_data)

@tasks.loop(seconds=30)
async def check_tickets():
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        return

    ticket_data = load_ticket_data()
    now = datetime.datetime.now(pytz.utc)
    changed = False

    for channel in guild.text_channels:
        if "ticket-" not in channel.name.lower():
            continue

        channel_id = str(channel.id)
        data = ticket_data.get(channel_id, {})

        if data.get("pinged", False):
            continue

        last_ts_str = data.get("last_non_admin_ts")
        if not last_ts_str:
            continue

        last_ts = datetime.datetime.fromisoformat(last_ts_str)
        if last_ts.tzinfo is None:
            last_ts = last_ts.replace(tzinfo=pytz.utc)

        if (now - last_ts).total_seconds() >= 600:  # 10 минут
            try:
                await channel.send(f"<@{ALLOWED_USER_ID}>")
                ticket_data[channel_id]["pinged"] = True
                changed = True
                print(f"[INFO] Пинг отправлен в тикет {channel.name}")
            except Exception as e:
                print(f"[ERROR] Ошибка пинга в {channel.name}: {e}")

    if changed:
        save_ticket_data(ticket_data)

@check_tickets.before_loop
async def before_tickets():
    await bot.wait_until_ready()

    # Инициализация: считываем последнее сообщение в каждом тикете
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        return

    ticket_data = load_ticket_data()

    for channel in guild.text_channels:
        if "ticket-" not in channel.name.lower():
            continue

        channel_id = str(channel.id)
        if channel_id in ticket_data:
            continue  # Уже есть данные — не трогаем

        try:
            messages = [msg async for msg in channel.history(limit=1)]
            if messages:
                last_msg = messages[0]
                if last_msg.author.id != ALLOWED_USER_ID and not last_msg.author.bot:
                    ticket_data[channel_id] = {
                        "last_non_admin_ts": last_msg.created_at.isoformat(),
                        "pinged": False
                    }
                else:
                    ticket_data[channel_id] = {
                        "last_non_admin_ts": None,
                        "pinged": False
                    }
        except Exception as e:
            print(f"[ERROR] Инициализация тикета {channel.name}: {e}")

    save_ticket_data(ticket_data)
    print("[INFO] Тикеты инициализированы")

# ───────────────────────────────────────────────
#  Система акций
# ───────────────────────────────────────────────

@tasks.loop(seconds=1)
async def check_daily_promotion():
    try:
        msk = pytz.timezone('Europe/Moscow')
        now = datetime.datetime.now(msk)

        if now.date() != PROMO_DATE:
            return

        if now.hour != 0 or now.minute != 0:
            return

        promo_data = load_promo_data()

        if promo_data.get("sent", False):
            return

        channel = bot.get_channel(PROMO_CHANNEL_ID)
        if not channel:
            return

        # Удаляем старые сообщения
        if promo_data.get("last_gif_id"):
            try:
                old_gif = await channel.fetch_message(promo_data["last_gif_id"])
                await old_gif.delete()
            except:
                pass

        if promo_data.get("last_message_id"):
            try:
                old_msg = await channel.fetch_message(promo_data["last_message_id"])
                await old_msg.delete()
            except:
                pass

        # Отправляем GIF
        gif_url = random.choice(GIF_URLS)
        gif_embed = discord.Embed(color=COLOR)
        gif_embed.set_image(url=gif_url)
        gif_message = await channel.send(embed=gif_embed)

        # Отправляем акцию
        promo_message = await channel.send(
            embed=build_promo_embed("Акция действует только 23.02.2026")
        )

        promo_data["last_gif_id"] = gif_message.id
        promo_data["last_message_id"] = promo_message.id
        promo_data["sent"] = True
        save_promo_data(promo_data)

        print(f"[INFO] Акция 23 февраля отправлена в {now.strftime('%H:%M')}")

    except Exception as e:
        import traceback
        traceback.print_exc()

@check_daily_promotion.before_loop
async def before_promotion():
    await bot.wait_until_ready()

# ───────────────────────────────────────────────
#  Команды акций
# ───────────────────────────────────────────────

@bot.tree.command(name="stock", description="Отправить акцию 23 февраля для теста")
async def stock(interaction: discord.Interaction):
    if interaction.user.id != ALLOWED_USER_ID:
        await interaction.response.send_message("Нет доступа к этой команде.", ephemeral=True)
        return

    gif_url = random.choice(GIF_URLS)
    gif_embed = discord.Embed(color=COLOR)
    gif_embed.set_image(url=gif_url)
    await interaction.channel.send(embed=gif_embed)

    await interaction.channel.send(
        embed=build_promo_embed("Тестовая акция • Не является действительной")
    )
    await interaction.response.send_message("Тестовая акция отправлена!", ephemeral=True)

@bot.tree.command(name="resend_promo", description="Повторно отправить акцию 23 февраля")
@app_commands.describe(channel="Канал для отправки акции")
async def resend_promo(interaction: discord.Interaction, channel: discord.TextChannel):
    if interaction.user.id != ALLOWED_USER_ID:
        await interaction.response.send_message("Нет доступа к этой команде.", ephemeral=True)
        return

    gif_url = random.choice(GIF_URLS)
    gif_embed = discord.Embed(color=COLOR)
    gif_embed.set_image(url=gif_url)
    await channel.send(embed=gif_embed)

    await channel.send(embed=build_promo_embed("Акция действует только 23.02.2026"))
    await interaction.response.send_message(f"Акция отправлена в {channel.mention}", ephemeral=True)

# ───────────────────────────────────────────────
#  Команды проектов
# ───────────────────────────────────────────────

@bot.tree.command(name="set_project", description="Добавить или обновить проект пользователя")
@app_commands.describe(user="Пользователь", link="Ссылка на Figma проект")
async def set_project(interaction: discord.Interaction, user: discord.User, link: str):
    if interaction.user.id != ALLOWED_USER_ID:
        await interaction.response.send_message(
            "Нет доступа. [Нажмите для получения](https://t.me/kmdsgn)",
            ephemeral=True
        )
        return

    projects = load_projects()
    user_id = str(user.id)
    is_update = user_id in projects

    projects[user_id] = {
        "link": link,
        "added_at": datetime.datetime.now(pytz.timezone('Europe/Moscow')).strftime('%d.%m.%Y %H:%M')
    }
    save_projects(projects)

    action = "обновлён" if is_update else "добавлен"
    await interaction.response.send_message(
        f"Проект для {user.mention} успешно {action}!",
        ephemeral=False
    )

    try:
        dm_embed = discord.Embed(
            title="<:Vector1:1457389720270147634> - Ваш проект готов!",
            description=f"Ваш проект {'обновлён' if is_update else 'добавлен'}.\\nИспользуйте команду `/project` для просмотра ссылки.",
            color=COLOR
        )
        dm_embed.set_footer(text=f"Дата: {projects[user_id]['added_at']}")
        await user.send(embed=dm_embed)
    except discord.Forbidden:
        await interaction.followup.send(
            f"⚠️ Не удалось отправить ЛС {user.mention} (закрыты личные сообщения).",
            ephemeral=True
        )

@bot.tree.command(name="project", description="Получить ссылку на ваш проект")
async def project(interaction: discord.Interaction):
    projects = load_projects()
    user_id = str(interaction.user.id)

    if user_id not in projects:
        embed = discord.Embed(
            title="Проект не найден",
            description="<:Vector:1465793810909888749>ㅤ-ㅤУ вас нет сохранённых проектов.",
            color=COLOR
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    project_data = projects[user_id]
    embed = discord.Embed(
        title="<:Vector1:1457389720270147634> - Ваш Figma проект",
        description=f"[Открыть проект]({project_data['link']})",
        color=COLOR
    )
    embed.add_field(name="Ссылка", value=project_data['link'], inline=False)
    embed.set_footer(text=f"Добавлен: {project_data['added_at']}")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ───────────────────────────────────────────────
#  Напоминание о хостинге
# ───────────────────────────────────────────────

@tasks.loop(seconds=1)
async def check_hosting_reminder():
    msk = pytz.timezone('Europe/Moscow')
    now = datetime.datetime.now(msk)

    target_dates = [
        datetime.datetime(2026, 3, 1, 17, 0, tzinfo=msk),
        datetime.datetime(2026, 3, 2, 17, 0, tzinfo=msk)
    ]

    for target_date in target_dates:
        if abs((now - target_date).total_seconds()) < 3600:
            guild = bot.get_guild(GUILD_ID)
            if guild:
                channel = guild.text_channels[0] if guild.text_channels else None
            if channel:
                embed = discord.Embed(
                    title="⚠️ Хостинг истекает",
                    description="Максимка, забери мои файлы с хоста чтоб они не пропали (До 3 марта)",
                    color=0xFF0000
                )
                embed.set_footer(text=f"Напоминание от {now.strftime('%d.%m.%Y %H:%M')}")
                await channel.send(embed=embed)

@check_hosting_reminder.before_loop
async def before_reminder():
    await bot.wait_until_ready()

# ───────────────────────────────────────────────
#  Прайс-лист
# ───────────────────────────────────────────────

PRICES = {
    "ui": {
        "title": "ㅤ ㅤㅤㅤㅤ<:Vector1:1446817226886873202> — Дизайн интерфейсаㅤㅤㅤㅤㅤㅤ",
        "description": (
            "ㅤ\\n"
            "<:Group57:1382355478037794917> **GUI** ㅤ ㅤㅤ ㅤㅤㅤㅤㅤㅤㅤㅤ ㅤ ㅤㅤㅤ— ㅤ**` 1900 ₽ `**\\n"
            "<:Group57:1382355478037794917> **HUD** ㅤ ㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤ ㅤㅤㅤ— ㅤ**` 1100 ₽ `**\\n"
            "<:Group57:1382355478037794917> **MAIN MENU**ㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤ ㅤ— ㅤ**` 700 ₽ `**\\n"
            "<:Group57:1382355478037794917> **ALT MANAGER**ㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤ— ㅤ**` 900 ₽ `**\\n"
            "<:Group57:1382355478037794917> **LOADER**ㅤ ㅤㅤ ㅤ ㅤㅤㅤㅤㅤㅤㅤㅤ ㅤ — ㅤ**` 2000 ₽ `**\\n"
            "\\n"
            "<:Group57:1382355478037794917> **WEB (Главная)** ㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤ— ㅤ**` 700 ₽ `**\\n"
            "<:Group57:1382355478037794917> **WEB (Доп. страница)**ㅤ ㅤㅤㅤㅤㅤㅤㅤ — ㅤ**` 650 ₽ `**\\n"
            "ㅤ"
        )
    },
    "transfer": {
        "title": "ㅤㅤㅤㅤㅤ<:Vector2:1446817219488120873> — Перенос дизайна в кодㅤㅤㅤㅤㅤ",
        "description": (
            "ㅤ\\n"
            "<:Group57:1382355478037794917> **GUI** ㅤ ㅤㅤ ㅤㅤㅤ ㅤㅤㅤㅤㅤㅤ ㅤㅤㅤ— ㅤ**` 3000 ₽ `**\\n"
            "<:Group57:1382355478037794917> **HUD** ㅤ ㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤ ㅤㅤㅤ— ㅤ**` 1800 ₽ `**\\n"
            "<:Group57:1382355478037794917> **MAIN MENU**ㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤ ㅤ— ㅤ**` 800 ₽ `**\\n"
            "<:Group57:1382355478037794917> **ALT MANAGER**ㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤ— ㅤ**` 1000 ₽ `**\\n"
            "<:Group57:1382355478037794917> **ESP**ㅤㅤ ㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤ— ㅤ**` 600 ₽ `**\\n-# Стоимость переноса очень сильно зависит от дизайн проекта и предоставленной базы, она может быть как уменьшена так и увеличена. Вместе с дизайном реализуются базовые логики, для продвинутых потребуется доплата.\\n"
            "\\n"
            "<:Group57:1382355478037794917> **WEB (Главная)** ㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤ— ㅤ**` от 1000 ₽ `**\\n"
            "<:Group57:1382355478037794917> **WEB (Личный кабинет)**ㅤㅤㅤㅤㅤㅤ ㅤ — ㅤ**` от 1000 ₽ `**\\n"
            "<:Group57:1382355478037794917> **WEB (Регистрация)**ㅤㅤㅤㅤㅤㅤㅤㅤㅤ — ㅤ**` от 1000 ₽ `**\\n"
            "<:Group57:1382355478037794917> **WEB (Товары)**ㅤ ㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤ — ㅤ**` от 500 ₽ `**\\n"
            "<:Group57:1382355478037794917> **WEB (Доп. страница)**ㅤ ㅤㅤㅤㅤㅤㅤㅤ — ㅤ**` от 400 ₽ `**\\n"
            "ㅤ"
        )
    },
    "branding": {
        "title": "ㅤㅤㅤㅤ ㅤㅤㅤ<:Vector:1446817225314140351> — Оформлениеㅤㅤㅤㅤㅤㅤㅤ",
        "description": (
            "ㅤ\\n"
            "<:Group57:1382355478037794917> **Аватарка (3D Анимация)** ㅤㅤㅤㅤㅤㅤ — ㅤ**` 500 ₽ `**\\n"
            "<:Group57:1382355478037794917> **Аватарка (Статичная)**ㅤ ㅤㅤㅤㅤㅤㅤ — ㅤ**` 400 ₽ `**\\n"
            "<:Group57:1382355478037794917> **Баннер (3D Статичная)**ㅤㅤㅤㅤㅤ ㅤㅤ — ㅤ**` 300 ₽ `**\\n"
            "<:Group57:1382355478037794917> **Привью (YouTube)**ㅤㅤㅤㅤㅤㅤㅤ ㅤㅤ — ㅤ**` 400 ₽ `**\\n"
            "<:Group57:1382355478037794917> **Логотип**ㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤ— ㅤ**` 100 ₽ `**\\n-# Приобрести логотип можно только заказав вместе\\n-# с ним услугу для которой он понадобится.\\n"
            "ㅤ"
        )
    },
    "game": {
        "title": "ㅤㅤㅤㅤㅤㅤㅤㅤㅤ<:Vector3:1446817221031624816> — Играㅤㅤㅤㅤㅤㅤㅤㅤㅤ",
        "description": (
            "ㅤ\\n"
            "<:Group57:1382355478037794917> **Плащ**ㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤ — ㅤ**` 300 ₽ `**\\n"
            "<:Group57:1382355478037794917> **Плащ (Анимация)**ㅤㅤㅤㅤㅤㅤㅤㅤ ㅤ — ㅤ**` 450 ₽ `**\\n"
            "<:Group57:1382355478037794917> **Target ESP (Маркер)**ㅤㅤㅤㅤㅤㅤ ㅤ ㅤ — ㅤ**` 100 ₽ `**\\n"
            "<:Group57:1382355478037794917> **Arrow**ㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤ ㅤㅤ— ㅤ**` 100 ₽ `**\\n"
            "<:Group57:1382355478037794917> **Entity ESP**ㅤㅤㅤㅤㅤ ㅤㅤㅤㅤㅤㅤㅤㅤ — ㅤ**` 400 ₽ `**\\n"
            "ㅤ"
        )
    },
    "other": {
        "title": "ㅤㅤㅤㅤㅤㅤㅤㅤ<:Vector4:1446817223317520394> — Другоеㅤㅤㅤㅤㅤㅤㅤㅤㅤ",
        "description": (
            "ㅤ\\n"
            "<:Group57:1382355478037794917> **Обход очереди**ㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤ— ㅤ**` 55% `**\\n-# Приобрести обход очереди можно только\\n-# если стоимость вашего заказа больше 1000₽.\\n"
            "ㅤ"
        )
    }
}

class CategorySelect(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        options = [
            discord.SelectOption(
                label="Дизайн интерфейса",
                value="ui",
                description="UX/UI, сайты, клиенты, приложения",
                emoji="<:Vector1:1446817226886873202>"
            ),
            discord.SelectOption(
                label="Перенос дизайна",
                value="transfer",
                description="Перенос из дизайн проекта в код",
                emoji="<:Vector2:1446817219488120873>"
            ),
            discord.SelectOption(
                label="Оформление",
                value="branding",
                description="Баннеры, привью, оформление серверов",
                emoji="<:Vector:1446817225314140351>"
            ),
            discord.SelectOption(
                label="Игра",
                value="game",
                description="ESP, плащи, и всё, что связано с игрой",
                emoji="<:Vector3:1446817221031624816>"
            ),
            discord.SelectOption(
                label="Другое",
                value="other",
                description="Обход очереди, индивидуальные запросы",
                emoji="<:Vector4:1446817223317520394>"
            ),
        ]

        select = discord.ui.Select(
            placeholder="Категория",
            options=options,
            min_values=1,
            max_values=1,
            custom_id="category_select"
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        value = interaction.data["values"][0]
        data = PRICES.get(value)

        embed = discord.Embed(
            title=data["title"],
            description=data["description"],
            color=COLOR
        )
        embed.set_footer(text="ㅤㅤㅤЦены услуг могут изменяться от объема и их сложности.ㅤㅤ")
        await interaction.response.send_message(embed=embed, ephemeral=True)

# ───────────────────────────────────────────────
#  /msg
# ───────────────────────────────────────────────

@bot.tree.command(name="msg", description="Отправить сообщение в канал")
@app_commands.describe(channel="Канал, в который отправить сообщение (если не указан — текущий)")
@app_commands.describe(type="Тип сообщения для отправки")
@app_commands.choices(type=[
    app_commands.Choice(name="Магазин (SHOP)", value="SHOP"),
    app_commands.Choice(name="Информация (INFO)", value="INFO"),
    app_commands.Choice(name="Правила (RULES)", value="RULES"),
])
async def msg(
    interaction: discord.Interaction,
    type: str = "SHOP",
    channel: discord.TextChannel | None = None
):
    if interaction.user.id != ALLOWED_USER_ID:
        await interaction.response.send_message(
            "Нет доступа. [Нажмите для получения](https://t.me/kmdsgn)",
            ephemeral=True
        )
        return

    target_channel = channel or interaction.channel

    if type == "SHOP":
        embed_price = discord.Embed(
            title="ㅤ ㅤㅤ  ㅤ<:Group56:1382349433966034974> — Стоимость наших услугㅤㅤㅤㅤㅤ",
            color=COLOR
        )
        embed_select = discord.Embed(
            title="ㅤㅤㅤВыберите интересующую категориюㅤㅤㅤ",
            description=(
                "ㅤРаскройте меню ниже и выберите категорию, чтобы\\n"
                "ㅤㅤㅤполучить список услуг и примерные цены."
            ),
            color=COLOR
        )
        view = CategorySelect()
        await target_channel.send(embeds=[embed_price, embed_select], view=view)

    elif type == "INFO":
        embed_info = discord.Embed(
            title="Информация о магазине",
            description=(
                "Мы предоставляем услуги по дизайну интерфейсов, оформлению и игровой графике.\\n"
                "Для заказа используйте команду /msg и выберите нужную категорию."
            ),
            color=COLOR
        )
        await target_channel.send(embed=embed_info)

    elif type == "RULES":
        embed_rules = discord.Embed(
            title="Правила магазина",
            description=(
                "1. Предоплата 50% до начала работы\\n"
                "2. Сроки обсуждаются индивидуально\\n"
                "3. Правки вносятся в течение 3 дней после сдачи"
            ),
            color=COLOR
        )
        await target_channel.send(embed=embed_rules)

    await interaction.response.send_message(
        f"Сообщение типа `{type}` отправлено в {target_channel.mention}",
        ephemeral=True
    )

# ───────────────────────────────────────────────
#  on_ready
# ───────────────────────────────────────────────

@bot.event
async def on_ready():
    print(f"[INFO] Бот запущен как {bot.user} (ID: {bot.user.id})")
    bot.add_view(CategorySelect())
    check_hosting_reminder.start()
    check_daily_promotion.start()
    check_tickets.start()
    print("[INFO] Все таски запущены")

    try:
        await bot.tree.sync()
        print("[INFO] Команды синхронизированы")
    except Exception as e:
        print(f"[ERROR] Ошибка синхронизации команд: {e}")

if __name__ == "__main__":
    bot.run(TOKEN)