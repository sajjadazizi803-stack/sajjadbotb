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
import requests
from deep_translator import GoogleTranslator

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
        ["اخبار کریپتو"],
        ["بازگشت"],
    ],
    resize_keyboard=True,
)


# ------------------ START ------------------


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("به ربات خوش آمدید.", reply_markup=MAIN_KEYBOARD)


# ------------------ ABOUT ------------------


async def about_me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(ABOUT_TEXT)


# ------------------ SERVICES ------------------


async def services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(SERVICES_TEXT, reply_markup=SERVICES_KEYBOARD)


async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "به منوی اصلی بازگشتید.", reply_markup=MAIN_KEYBOARD
    )


# ------------------ CONTACT ------------------


async def contact_me(update: Update, context: ContextTypes.DEFAULT_TYPE):

    print("contact_me اجرا شد")

    context.user_data["contact_mode"] = True

    print(context.user_data)

    await update.message.reply_text(CONTACT_TEXT)


# ------------------ SEND TO ADMIN ------------------


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


# ------------------ HANDLERS ------------------


def get_handlers():

    return [
        CommandHandler("start", start),
        MessageHandler(filters.Regex("^👨‍💻 درباره‌ی من$"), about_me),
        MessageHandler(filters.Regex("^🛠 خدمات$"), services),
        MessageHandler(filters.Regex("^بازگشت$"), back_to_main),
        MessageHandler(filters.Regex("^اخبار کریپتو$"), crypto_news),
        MessageHandler(filters.Regex("^💬 ارتباط با من$"), contact_me),
        CallbackQueryHandler(next_news, pattern="next_news"),
        MessageHandler(
            filters.User(ADMIN_ID) & filters.REPLY & ~filters.COMMAND, admin_reply
        ),
        MessageHandler(
            ~filters.User(ADMIN_ID) & filters.ALL & ~filters.COMMAND, forward_to_admin
        ),
    ]
