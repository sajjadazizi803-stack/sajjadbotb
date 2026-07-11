from telegram import (
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Update,
)

from telegram.ext import (
    ContextTypes,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    filters,
)

from config import *

import feedparser
from telegram.error import Forbidden, BadRequest
import requests
from deep_translator import GoogleTranslator
from functools import wraps

ADMIN_WAITING_FOR_CONFIG = {}
ADMIN_WAITING_FOR_BROADCAST = set()

CHANNEL_USERNAME = "@SADSSCS"
CHANNEL_LINK = "https://t.me/SADSSCS"
USERS_FILE = "users.txt"

# ------------------ KEYBOARDS ------------------

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["💬 ارتباط با من"],
        ["🛠 خدمات"],
        ["👨‍💻 درباره‌ی من"],
    ],
    resize_keyboard=True,
)

SERVICES_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["📰 اخبار کریپتو", "🔐 کانفیگ VPN"],
        ["🔙 بازگشت"],
    ],
    resize_keyboard=True,
)

VPN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🎁 اشتراک تست"],
        ["💎 خرید اشتراک"],
        ["🔙 بازگشت"],
    ],
    resize_keyboard=True,
)

VPN_TEST_KEYBOARD = InlineKeyboardMarkup(
    [[InlineKeyboardButton("📥 دریافت اشتراک تست", callback_data="vpn_test")]]
)

# ------------------ check membership ------------------


async def check_membership(user_id, context):

    try:
        member = await context.bot.get_chat_member(
            chat_id=CHANNEL_USERNAME,
            user_id=user_id,
        )

        return member.status in (
            "member",
            "administrator",
            "creator",
        )

    except Exception:
        return False


# ------------------ membership guard ------------------


async def membership_guard(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    if await check_membership(user_id, context):
        return True

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📢 عضویت در کانال",
                    url=CHANNEL_LINK,
                )
            ],
            [
                InlineKeyboardButton(
                    "✅ عضو شدم",
                    callback_data="check_join",
                )
            ],
        ]
    )

    if update.callback_query:

        await update.callback_query.message.reply_text(
            """❌ هنوز عضو کانال نیستید.

برای استفاده از تمام امکانات ربات باید عضو کانال باشید.

👇 ابتدا عضو شوید و سپس روی «✅ عضو شدم» بزنید.""",
            reply_markup=keyboard,
        )

    else:

        await update.message.reply_text(
            """❌ هنوز عضو کانال نیستید.

برای استفاده از تمام امکانات ربات باید عضو کانال باشید.

👇 ابتدا عضو شوید و سپس روی «✅ عضو شدم» بزنید.""",
            reply_markup=keyboard,
        )

    return False


def membership_required(func):

    @wraps(func)
    async def wrapper(
        update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs
    ):

        if not await membership_guard(update, context):
            return

        return await func(update, context, *args, **kwargs)

    return wrapper


# ------------------ save user ------------------


def save_user(user):

    user_id = str(user.id)
    first_name = (user.first_name or "").replace("|", "")
    username = user.username or ""

    users = {}

    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()

                if not line:
                    continue

                parts = line.split("|")

                if len(parts) >= 3:
                    users[parts[0]] = (
                        parts[1],
                        parts[2],
                    )

    except FileNotFoundError:
        pass

    users[user_id] = (
        first_name,
        username,
    )

    with open(USERS_FILE, "w", encoding="utf-8") as f:
        for uid, data in users.items():
            f.write(f"{uid}|{data[0]}|{data[1]}\n")


# ------------------ START ------------------


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    save_user(update.effective_user)

    if not await check_membership(user_id, context):

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "📢 عضویت در کانال",
                        url=CHANNEL_LINK,
                    )
                ],
                [
                    InlineKeyboardButton(
                        "✅ عضو شدم",
                        callback_data="check_join",
                    )
                ],
            ]
        )

        await update.message.reply_text(
            """
🌸 سلام دوست عزیز، خوش اومدی.

برای استفاده از امکانات ربات، ابتدا باید عضو کانال رسمی ما بشی.

🎁 مزایای عضویت:

• دریافت اشتراک تست رایگان VPN
• اطلاع از بروزرسانی‌های ربات
• آموزش‌ها و اخبار

👇 بعد از عضویت روی دکمه «✅ عضو شدم» بزن.
""",
            reply_markup=keyboard,
        )

        return

    await update.message.reply_text(
        "🎉 به ربات خوش آمدید.",
        reply_markup=MAIN_KEYBOARD,
    )


# ------------------ ABOUT me ------------------


@membership_required
async def about_me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(ABOUT_TEXT)


# ------------------ SERVICES ------------------


@membership_required
async def services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(SERVICES_TEXT, reply_markup=SERVICES_KEYBOARD)


# ------------------ back to nenu ------------------


@membership_required
async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "به منوی اصلی بازگشتید.", reply_markup=MAIN_KEYBOARD
    )


# ------------------- vpn config ------------------


@membership_required
async def vpn_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        """🔐 خدمات VPN

یکی از گزینه‌های زیر را انتخاب کنید.

🎁 اشتراک تست
دریافت ۱۰ گیگ اینترنت با اعتبار ۳۰ روز

💎 خرید اشتراک
(به‌زودی فعال می‌شود)
""",
        reply_markup=VPN_KEYBOARD,
    )


# ------------------- vpn test ------------------


@membership_required
async def vpn_test(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        """🎁 اشتراک تست رایگان

به مناسبت استفاده از ربات، برای تمامی کاربران:

📦 حجم: ۱۰ گیگ
📅 اعتبار: ۳۰ روز

در صورت رضایت می‌توانید اشتراک کامل تهیه کنید.

برای ثبت درخواست روی دکمه زیر بزنید.""",
        reply_markup=VPN_TEST_KEYBOARD,
    )


# ------------------ vpn test request ------------------


@membership_required
async def vpn_test_request(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user = query.from_user

    text = f"""🆕 درخواست اشتراک تست VPN

👤 نام:
{user.full_name}

📛 یوزرنیم:
@{user.username if user.username else "-"}

🆔 User ID:
{user.id}
"""

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📤 ارسال کانفیگ", callback_data=f"send_config_{user.id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "❌ قبلاً تست دریافت کرده",
                    callback_data=f"already_received_{user.id}",
                )
            ],
        ]
    )

    await context.bot.send_message(chat_id=ADMIN_ID, text=text, reply_markup=keyboard)

    await query.edit_message_text("""✅ درخواست شما با موفقیت ثبت شد.

⏳ درخواست برای ادمین ارسال شد.

پس از بررسی، اشتراک تست از طریق همین ربات برای شما ارسال خواهد شد.""")


# ------------------ send config callback ------------------


@membership_required
async def send_config_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user_id = int(query.data.split("_")[-1])

    ADMIN_WAITING_FOR_CONFIG[query.from_user.id] = user_id

    await query.message.reply_text(
        "📤 لطفاً کانفیگ را ارسال کنید.\n\n" "کافی است متن کانفیگ را Paste کنید."
    )


# ------------------ already receive callback ------------------


@membership_required
async def already_received_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user_id = int(query.data.split("_")[-1])

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💎 خرید اشتراک", callback_data="buy_vpn")],
            [
                InlineKeyboardButton(
                    "💬 ارتباط با پشتیبانی", callback_data="contact_support"
                )
            ],
        ]
    )

    try:

        await context.bot.send_message(
            chat_id=user_id,
            text="""❌ درخواست شما بررسی شد.

متأسفانه طبق بررسی، شما قبلاً اشتراک تست رایگان را دریافت کرده‌اید.

💎 در صورت تمایل می‌توانید اشتراک اصلی را تهیه کنید.""",
            reply_markup=keyboard,
        )

        await query.message.reply_text("✅ پیام برای کاربر ارسال شد.")

    except Exception as e:

        print(e)

        await query.message.reply_text("❌ ارسال پیام با خطا مواجه شد.")


# ------------------ receive vpn config ------------------


@membership_required
async def receive_vpn_config(update: Update, context: ContextTypes.DEFAULT_TYPE):

    admin_id = update.effective_user.id

    print(ADMIN_WAITING_FOR_CONFIG)

    if admin_id not in ADMIN_WAITING_FOR_CONFIG:
        return

    user_id = ADMIN_WAITING_FOR_CONFIG[admin_id]

    config_text = update.message.text

    try:

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "📚 آموزش اتصال",
                        callback_data="vpn_guide",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "💎 خرید اشتراک",
                        callback_data="buy_vpn",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "💬 ارتباط با پشتیبانی",
                        callback_data="contact_support",
                    )
                ],
            ]
        )

        await context.bot.send_message(
            chat_id=user_id,
            text=f"""
🎉 <b>اشتراک تست شما آماده شد.</b>

━━━━━━━━━━━━━━

🎁 <b>اشتراک تست رایگان</b>

📦 حجم:
<b>10 گیگابایت</b>

📅 اعتبار:
<b>30 روز</b>

━━━━━━━━━━━━━━

🔐 <b>کانفیگ شما:</b>

<code>{config_text}</code>

━━━━━━━━━━━━━━

⚠️ لطفاً این کانفیگ را در اختیار دیگران قرار ندهید.

❤️ در صورت رضایت از کیفیت سرویس، می‌توانید اشتراک اصلی را تهیه کنید.
""",
            parse_mode="HTML",
            reply_markup=keyboard,
        )

        await update.message.reply_text("✅ کانفیگ با موفقیت برای کاربر ارسال شد.")

    except Exception as e:

        print(e)

        await update.message.reply_text("❌ ارسال کانفیگ با خطا مواجه شد.")

    del ADMIN_WAITING_FOR_CONFIG[admin_id]


# ------------------ receive broadcast ------------------


async def receive_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        return

    if update.effective_user.id not in ADMIN_WAITING_FOR_BROADCAST:
        return

    ADMIN_WAITING_FOR_BROADCAST.remove(update.effective_user.id)

    text = update.message.text

    success = 0
    failed = 0

    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = [line.strip().split("|")[0] for line in f if line.strip()]

    except FileNotFoundError:
        users = []

    for user_id in users:

        try:

            await context.bot.send_message(
                chat_id=int(user_id),
                text=text,
            )

            success += 1

        except (Forbidden, BadRequest):

            failed += 1

            try:

                with open(USERS_FILE, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                with open(USERS_FILE, "w", encoding="utf-8") as f:
                    for line in lines:
                        if not line.startswith(f"{user_id}|"):
                            f.write(line)

            except Exception:
                pass

        except Exception:

            failed += 1

    await update.message.reply_text(
        f"""
✅ پیام همگانی ارسال شد.

━━━━━━━━━━━━━━

📨 ارسال موفق:
<b>{success}</b>

❌ ارسال ناموفق:
<b>{failed}</b>
""",
        parse_mode="HTML",
    )


# ------------------ admin text router ------------------


async def admin_text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):

    admin_id = update.effective_user.id

    if admin_id in ADMIN_WAITING_FOR_CONFIG:
        await receive_vpn_config(update, context)
        return

    if admin_id in ADMIN_WAITING_FOR_BROADCAST:
        await receive_broadcast(update, context)
        return


# ------------------ buy vpn callback ------------------


@membership_required
async def buy_vpn_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    await query.message.reply_text("""💎 خرید اشتراک

🚧 این بخش در حال آماده‌سازی است.

به‌زودی امکان خرید اشتراک از طریق ربات فعال خواهد شد.

🙏 از صبر و همراهی شما متشکریم. ❤️""")


# ------------------ vpn guide callback ------------------


@membership_required
async def vpn_guide_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    await query.message.reply_text(
        """
📚 <b>راهنمای استفاده از کانفیگ</b>

برای استفاده از کانفیگ، ابتدا برنامه <b>NPV Tunnel</b> را نصب کنید.

📥 <a href="https://play.google.com/store/apps/details?id=com.napsternetlabs.napsternetv">دانلود NPV Tunnel از Google Play</a>

یا می‌توانید از برنامه <b>V2RayNG</b> و سایر کلاینت‌های V2Ray نیز استفاده کنید؛
پیشنهاد ما NPV Tunnel و V2RayNG است.

━━━━━━━━━━━━━━

📖 <b>آموزش اتصال با NPV Tunnel</b>

1️⃣ کانفیگی که ربات برایتان ارسال کرده را <b>کپی</b> کنید.

2️⃣ وارد برنامه <b>NPV Tunnel</b> شوید.

3️⃣ از نوار پایین وارد بخش <b>Configs</b> شوید.

4️⃣ روی علامت <b>➕</b> بالای صفحه بزنید.
(محل آن بسته به زبان گوشی ممکن است سمت راست یا چپ باشد.)

5️⃣ گزینه:

<b>Import config from clipboard</b>

را انتخاب کنید.

6️⃣ سپس گزینه:

<b>V2Ray Config</b>

را بزنید.

7️⃣ کانفیگ شما اضافه شد.

8️⃣ از نوار پایین وارد بخش <b>Home</b> شوید.

9️⃣ کانفیگ را انتخاب کرده و روی <b>Connect</b> بزنید.

🎉 تمام!
اگر مراحل را درست انجام داده باشید، VPN شما متصل خواهد شد.

💬 اگر در هر مرحله به مشکلی برخورد کردید، از طریق بخش «ارتباط با پشتیبانی» با ما در ارتباط باشید.
""",
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


# ------------------ SEND TO ADMIN ------------------


@membership_required
async def forward_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):

    # پیام‌های ادمین را پردازش نکن
    if update.effective_user.id == ADMIN_ID:
        return

    if not context.user_data.get("contact_mode"):
        return

    user = update.effective_user

    caption = (
        f"📩 پیام جدید\n\n"
        f"👤 نام: {user.full_name}\n"
        f"🆔 آیدی عددی: {user.id}\n"
        f"📎 برای پاسخ روی همین پیام ریپلای کن."
    )

    try:

        await context.bot.send_message(ADMIN_ID, caption)

        await update.message.forward(chat_id=ADMIN_ID)

        await update.message.reply_text("✅ پیام شما ارسال شد.")

        context.user_data["contact_mode"] = False

    except Exception as e:
        print(e)


# ------------------ ADMIN REPLY ------------------

import re
import traceback


async def admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):

    # فقط ادمین اجازه پاسخ دارد
    if update.effective_user.id != ADMIN_ID:
        return

    # باید روی یک پیام ریپلای شده باشد
    if not update.message.reply_to_message:
        return

    try:
        reply = update.message.reply_to_message

        if not reply.text:
            return

        # پیدا کردن آیدی عددی با Regex
        match = re.search(r"🆔\s*آیدی عددی:\s*(\d+)", reply.text)

        if not match:
            return

        user_id = int(match.group(1))

        # ارسال پاسخ برای کاربر
        await context.bot.send_message(
            chat_id=user_id,
            text=("📬 <b>پاسخ مدیر</b>\n\n" f"{update.message.text}"),
            parse_mode="HTML",
        )

        # پیام موفقیت برای ادمین
        await update.message.reply_text("✅ پاسخ با موفقیت برای کاربر ارسال شد.")

    except Exception:
        traceback.print_exc()
        await update.message.reply_text(
            "❌ هنگام ارسال پاسخ خطایی رخ داد. خطا داخل ترمینال چاپ شد."
        )

        # ------------------ CRYPTO NEWS ------------------


@membership_required
async def crypto_news(update: Update, context: ContextTypes.DEFAULT_TYPE):

    waiting_message = await update.message.reply_text(
        "🤖⏳\n\n"
        "لطفاً کمی صبر کنید ....\n\n"
        "📰 در حال دریافت و آماده‌سازی اخبار کریپتو هستیم.\n"
        "این فرآیند ممکن است چند لحظه زمان ببرد 🙏✨"
    )

    try:

        response = requests.get(
            "https://newsdata.io/api/1/news",
            params={
                "apikey": GNEWS_API_KEY,
                "q": "cryptocurrency OR bitcoin OR ethereum OR solana",
                "language": "en",
                "size": NEWS_COUNT,
            },
            timeout=30,
        )

        data = response.json()

        if data.get("status") != "success":
            await update.message.reply_text(
                "❌ متأسفانه دریافت اخبار با مشکل مواجه شد.\n"
                "لطفاً چند لحظه بعد دوباره امتحان کنید."
            )
            return

        # حذف خبرهای تکراری و بدون عکس
        unique_news = []
        seen_titles = set()

        for item in data.get("results", []):

            title = item.get("title", "").strip()

            if title and title not in seen_titles and item.get("image_url"):
                seen_titles.add(title)
                unique_news.append(item)

        if not unique_news:
            await update.message.reply_text("❌ خبر مناسبی پیدا نشد.")
            return

        context.user_data["news_entries"] = unique_news
        context.user_data["news_index"] = 0

        news = unique_news[0]

        try:
            title = GoogleTranslator(source="auto", target="fa").translate(
                news["title"]
            )
        except:
            title = news["title"]

        description = ""

        if news.get("description"):

            try:
                description = GoogleTranslator(source="auto", target="fa").translate(
                    news["description"]
                )
            except:
                description = news["description"]

        MAX_DESCRIPTION = 450

        if description:

            description = description.strip()

            if len(description) > MAX_DESCRIPTION:
                description = description[:MAX_DESCRIPTION].rsplit(" ", 1)[0] + "..."

        caption = f"""📰 خبر شماره 1

📌 {title}

📝 {description}

🌐 منبع: {news.get("source_id", "-")}"""

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("📰 خبر بعدی", callback_data="next_news"),
                    InlineKeyboardButton(
                        "📖 مطالعه خبر", url=news.get("link", "https://newsdata.io/")
                    ),
                ]
            ]
        )

        await waiting_message.delete()

        await update.message.reply_photo(
            photo=news["image_url"], caption=caption, reply_markup=keyboard
        )

    except Exception as e:

        print(e)

        await update.message.reply_text("❌ خطا در دریافت اخبار.")


# ------------------ NEXT NEWS ------------------


@membership_required
async def next_news(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    news_entries = context.user_data.get("news_entries", [])

    if not news_entries:
        await query.message.reply_text("❌ خبری یافت نشد.")
        return

    index = context.user_data.get("news_index", 0)

    index += 1

    if index >= len(news_entries):
        index = 0

    context.user_data["news_index"] = index

    news = news_entries[index]

    try:
        title = GoogleTranslator(source="auto", target="fa").translate(news["title"])
    except:
        title = news["title"]

    description = ""

    if news.get("description"):

        try:
            description = GoogleTranslator(source="auto", target="fa").translate(
                news["description"]
            )
        except:
            description = news["description"]

    MAX_DESCRIPTION = 450

    if description:

        description = description.strip()

        if len(description) > MAX_DESCRIPTION:
            description = description[:MAX_DESCRIPTION].rsplit(" ", 1)[0] + "..."

    caption = f"""📰 خبر شماره {index + 1}

📌 {title}

📝 {description}

🌐 منبع: {news.get("source_id", "-")}"""

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📰 خبر بعدی", callback_data="next_news"),
                InlineKeyboardButton(
                    "📖 مطالعه خبر", url=news.get("link", "https://newsdata.io/")
                ),
            ]
        ]
    )

    try:
        await query.message.delete()
    except:
        pass

    try:

        await context.bot.send_photo(
            chat_id=query.message.chat.id,
            photo=news["image_url"],
            caption=caption,
            reply_markup=keyboard,
        )

    except Exception as e:

        print(news["image_url"])
        print(e)

        await context.bot.send_message(
            chat_id=query.message.chat.id,
            text=caption,
            reply_markup=keyboard,
        )


# ------------------ contact support callback ------------------


@membership_required
async def contact_support_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    context.user_data["contact_mode"] = True

    await query.message.reply_text(
        """💬 ارتباط با پشتیبانی

پیام خود را ارسال کنید.

پیام شما مستقیماً برای ادمین ارسال می‌شود و پاسخ نیز از طریق همین ربات برایتان ارسال خواهد شد."""
    )


# ------------------ contact me ------------------


@membership_required
async def contact_me(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data["contact_mode"] = True

    await update.message.reply_text(
        """💬 ارتباط با پشتیبانی

پیام خود را ارسال کنید.

پیام شما مستقیماً برای ادمین ارسال می‌شود و پاسخ نیز از طریق همین ربات برایتان ارسال خواهد شد."""
    )


# ------------------- buy vpn ------------------


@membership_required
async def buy_vpn(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text("""💎 خرید اشتراک

🚧 این بخش در حال آماده‌سازی است.

به‌زودی امکان خرید اشتراک از طریق ربات فعال خواهد شد.

🙏 از صبر و همراهی شما متشکریم. ❤️""")


# ------------------ check join callback ------------------


async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if await check_membership(user_id, context):

        await query.message.delete()

        await context.bot.send_message(
            chat_id=user_id,
            text="🎉 عضویت شما تأیید شد.\n\nبه ربات خوش آمدید 🌸",
            reply_markup=MAIN_KEYBOARD,
        )

    else:

        await query.answer()

        await query.message.reply_text(
            """
❌ هنوز عضو کانال نشدی.

برای استفاده از ربات ابتدا باید عضو کانال بشی.

👇 بعد از عضویت دوباره روی «✅ عضو شدم» بزن.
""",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "📢 عضویت در کانال",
                            url=CHANNEL_LINK,
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "✅ عضو شدم",
                            callback_data="check_join",
                        )
                    ],
                ]
            ),
        )


# ------------------ admin panel ------------------


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        return

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📊 آمار کاربران",
                    callback_data="admin_stats",
                )
            ],
            [
                InlineKeyboardButton(
                    "📢 پیام همگانی",
                    callback_data="admin_broadcast",
                )
            ],
            [
                InlineKeyboardButton(
                    "📥 درخواست‌های VPN",
                    callback_data="admin_vpn",
                )
            ],
        ]
    )

    await update.message.reply_text(
        """
⚙️ <b>پنل مدیریت</b>

یکی از گزینه‌های زیر را انتخاب کنید.
""",
        parse_mode="HTML",
        reply_markup=keyboard,
    )


# ------------------- stats ------------------


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        return

    try:

        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = [line for line in f.readlines() if line.strip()]

        total_users = len(users)

    except FileNotFoundError:
        total_users = 0

    await update.message.reply_text(
        f"""
📊 <b>آمار ربات</b>

━━━━━━━━━━━━━━

👥 تعداد کاربران:
<b>{total_users}</b>

📁 فایل کاربران:
<code>{USERS_FILE}</code>

✅ وضعیت:
<b>فعال</b>
""",
        parse_mode="HTML",
    )


# ------------------- admin stats callback ------------------


async def admin_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = [line for line in f.readlines() if line.strip()]

        total_users = len(users)

    except FileNotFoundError:
        total_users = 0

    await query.edit_message_text(
        f"""
📊 <b>آمار ربات</b>

━━━━━━━━━━━━━━

👥 تعداد کاربران:
<b>{total_users}</b>

📁 فایل کاربران:
<code>{USERS_FILE}</code>

✅ وضعیت:
<b>فعال</b>
""",
        parse_mode="HTML",
    )


# ------------------- admin broadcast callback ------------------


async def admin_broadcast_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    ADMIN_WAITING_FOR_BROADCAST.add(query.from_user.id)

    await query.edit_message_text(
        """
📢 <b>ارسال پیام همگانی</b>

پیام موردنظر را ارسال کنید.

هر متنی که ارسال کنید، برای تمام کاربران ربات فرستاده خواهد شد.

❌ برای لغو کافیست /start را بزنید.
""",
        parse_mode="HTML",
    )


# ------------------- HANDLERS ------------------


def get_handlers():

    return [
        CommandHandler("admin", admin_panel),
        CommandHandler("stats", stats),
        CommandHandler("start", start),
        MessageHandler(filters.Regex("^👨‍💻 درباره‌ی من$"), about_me),
        MessageHandler(filters.Regex("^🛠 خدمات$"), services),
        MessageHandler(filters.Regex("^🔙 بازگشت$"), back_to_main),
        MessageHandler(filters.Regex("^🔐 کانفیگ VPN$"), vpn_menu),
        MessageHandler(filters.Regex("^🎁 اشتراک تست$"), vpn_test),
        MessageHandler(filters.Regex("^💎 خرید اشتراک$"), buy_vpn),
        MessageHandler(filters.Regex("^📰 اخبار کریپتو$"), crypto_news),
        MessageHandler(filters.Regex("^💬 ارتباط با من$"), contact_me),
        CallbackQueryHandler(check_join_callback, pattern="^check_join$"),
        CallbackQueryHandler(next_news, pattern="next_news"),
        CallbackQueryHandler(vpn_test_request, pattern="^vpn_test$"),
        CallbackQueryHandler(send_config_callback, pattern="^send_config_"),
        CallbackQueryHandler(already_received_callback, pattern="^already_received_"),
        CallbackQueryHandler(contact_support_callback, pattern="^contact_support$"),
        CallbackQueryHandler(
            admin_stats_callback,
            pattern="^admin_stats$",
        ),
        CallbackQueryHandler(
            admin_broadcast_callback,
            pattern="^admin_broadcast$",
        ),
        CallbackQueryHandler(vpn_guide_callback, pattern="^vpn_guide$"),
        CallbackQueryHandler(buy_vpn_callback, pattern="^buy_vpn$"),
        # پاسخ ادمین به کاربران
        MessageHandler(
            filters.User(ADMIN_ID) & filters.REPLY & ~filters.COMMAND,
            admin_reply,
        ),
        MessageHandler(
            filters.User(ADMIN_ID) & filters.TEXT & ~filters.COMMAND,
            admin_text_router,
        ),
        # پیام کاربران برای ادمین
        MessageHandler(
            ~filters.User(ADMIN_ID) & filters.ALL & ~filters.COMMAND,
            forward_to_admin,
        ),
    ]
