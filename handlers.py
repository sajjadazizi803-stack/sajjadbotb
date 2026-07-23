from datetime import datetime, timedelta
import time
import random
import base64
from functools import wraps
from urllib.parse import quote
from config import ADMIN_ID
from telegram import ReplyKeyboardRemove
from market_api import get_market_prices

from telegram import (
    BotCommand,
    BotCommandScopeChat,
    BotCommandScopeDefault,
)

import feedparser
import jdatetime
import requests
from deep_translator import GoogleTranslator
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.error import Forbidden, BadRequest
from telegram.ext import (
    ContextTypes,
    MessageHandler,
    CommandHandler,
    TypeHandler,
    ApplicationHandlerStop,
    CallbackQueryHandler,
    filters,
)

from config import *

from database import (
    add_user,
    get_users,
    get_users_count,
    save_referral,
    has_referral,
    get_referrals_count,
    get_inviter,
    reward_already_paid,
    mark_reward_paid,
    add_balance,
    get_balance,
    deduct_balance,
    get_referrals,
    set_news,
    get_news,
    get_join_date,
    get_referral_earnings,
    save_user_service,
    get_subscription_by_service,
    get_subscription_by_service_name,
    get_service_by_name,
    update_service_configs,
    get_service_configs_db,
    update_service_region,
    get_service_region,
    update_service_name,
    get_user_services,
)

from nahan_api import (
    create_nahan_user,
    rename_service,
    get_user_services as get_nahan_user_services,
    get_service_by_id,
    get_service_configs,
    test_patch_user,
    test_api_root,
)

ADMIN_WAITING_FOR_CONFIG = {}
ADMIN_WAITING_FOR_BROADCAST = set()
ADMIN_WAITING_FOR_SUB = {}

CHANNEL_USERNAME = "@SADSSCS"
CHANNEL_LINK = "https://t.me/SADSSCS"


# ------------------ admin only ------------------

from functools import wraps


def admin_only(func):

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):

        if update.effective_user.id != ADMIN_ID:
            return

        return await func(update, context)

    return wrapper


# ------------------ KEYBOARDS ------------------

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🛠 خدمات"],
        ["💬 ارتباط با پشتیبانی", "👤 پروفایل"],
        ["👨‍💻 سازنده ربات"],
    ],
    resize_keyboard=True,
)

SERVICES_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🛰️ داشبورد اخبار راهبردی", "🔐 کانفیگ VPN"],
        ["🔙 بازگشت"],
    ],
    resize_keyboard=True,
)

VPN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🎁 اشتراک تست", "💎 خرید اشتراک"],
        ["📦 اشتراک‌های من", "👥 زیرمجموعه گیری"],
        ["📚 آموزش اتصال", "🔙 بازگشت"],
    ],
    resize_keyboard=True,
)

VPN_TEST_KEYBOARD = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton(
                "🎁 دریافت اشتراک تست",
                callback_data="vpn_test_request",
            )
        ]
    ]
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


# ------------------ global membership check ------------------


from telegram.ext import ApplicationHandlerStop


async def global_membership_check(update: Update, context: ContextTypes.DEFAULT_TYPE):

    # اجازه بده /start خودش اجرا شود
    if (
        update.message
        and update.message.text
        and update.message.text.startswith("/start")
    ):
        return

    # اجازه بده دکمه "عضو شدم" همیشه کار کند
    if update.callback_query and update.callback_query.data == "check_join":
        return

    # اگر عضو است، ادامه بده
    if await membership_guard(update, context):
        return

    # اجرای سایر هندلرها متوقف می‌شود
    raise ApplicationHandlerStop


# ------------------ save user ------------------


def save_user(user):

    add_user(
        user.id,
        user.username or "",
        user.full_name,
    )


# ------------------ START ------------------


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    add_user(
        update.effective_user.id,
        update.effective_user.username,
        update.effective_user.full_name,
    )

    args = context.args

    if args:
        try:
            inviter_id = int(args[0])

            if inviter_id != user_id:

                if not has_referral(user_id):
                    save_referral(user_id, inviter_id)

        except Exception:
            pass

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
👋 سلام به ربات خوش اومدید.

برای استفاده از امکانات ربات، ابتدا باید در کانال‌های زیر عضو شوید. 📢

پس از عضویت، روی دکمه «عضو شدم ✅️» کلیک کنید.
""",
            reply_markup=keyboard,
        )

        return

    if update.effective_chat.type == "private":

        await update.message.reply_text(
            "🎉 به ربات خوش آمدید.",
            reply_markup=MAIN_KEYBOARD,
        )

    else:

        await update.message.reply_text(
            "🎉 به ربات خوش آمدید.",
        )


# ------------------ ABOUT me ------------------

from telegram.constants import ParseMode


@membership_required
async def about_me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        ABOUT_TEXT, parse_mode=ParseMode.HTML, disable_web_page_preview=True
    )


# ------------------ SERVICES ------------------


@membership_required
async def services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(SERVICES_TEXT, reply_markup=SERVICES_KEYBOARD)


# ------------------ back to main ------------------


@membership_required
async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":

        await update.message.reply_text(
            "به منوی اصلی بازگشتید.",
            reply_markup=MAIN_KEYBOARD,
        )

    else:

        await update.message.reply_text(
            "به منوی اصلی بازگشتید.",
        )


# ------------------- vpn menu ------------------


@membership_required
async def vpn_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        """🔐 خدمات کانفیگ

لطفا یکی از گزینه‌های زیر را انتخاب کنید:
""",
        reply_markup=VPN_KEYBOARD,
    )


# ------------------- vpn test ------------------


@membership_required
async def vpn_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    balance = get_balance(update.effective_user.id)

    await update.message.reply_text(
        f"""🎁 اشتراک تست

💰 قیمت اشتراک تست: 5,000 تومان
💳 اعتبار فعلی شما: {balance:,} تومان

📦 مشخصات اشتراک:
• حجم: 1 گیگ
• مدت: 30 روز

👇 برای دریافت اشتراک، روی دکمه «🎁 دریافت اشتراک تست» بزنید.""",
        reply_markup=VPN_TEST_KEYBOARD,
    )


# ------------------ get vless config ------------------


def get_vless_configs(subscription_url):

    try:

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "*/*",
        }

        r = requests.get(
            subscription_url,
            headers=headers,
            timeout=20,
        )

        if r.status_code != 200:
            return []

        text = r.text.strip()

        if not text:
            return []

        try:
            decoded = base64.b64decode(text + "=" * (-len(text) % 4)).decode(
                "utf-8",
                errors="ignore",
            )
        except Exception:
            decoded = text

        configs = []
        seen = set()

        for line in decoded.splitlines():

            line = line.strip()

            if not line.startswith("vless://"):
                continue

            if line in seen:
                continue

            seen.add(line)
            configs.append(line)

        return configs

    except Exception as e:
        return []


# ------------------ show configs ------------------


async def show_configs(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer(
        "⏳ در حال دریافت کانفیگ‌ها...",
        show_alert=False,
    )

    if query.data.startswith("show_configs_"):
        service_id = query.data.replace("show_configs_", "")
    else:
        service_id = context.user_data.get("subscription_service_id")

    if not service_id:
        await query.answer(
            "❌ سرویس پیدا نشد.",
            show_alert=True,
        )
        return

    configs = get_service_configs_db(service_id)

    if not configs:
        await query.answer(
            "❌ کانفیگی برای این سرویس ذخیره نشده است.",
            show_alert=True,
        )
        return

    all_configs = "\n\n".join(configs)

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "⬅️ بازگشت",
                    callback_data="back_to_subscription",
                )
            ]
        ]
    )

    await query.edit_message_text(
        f"""📄 <b>کانفیگ‌های VLESS</b>

<code>{all_configs}</code>

<b>📋 برای کپی، روی متن بالا ضربه بزنید.</b>
این کانفیگ‌ها را می‌توانید در
<b>V2RayNG</b>،
<b>NekoBox</b>،
<b>V2Box</b>،
<b>Hiddify</b>
و سایر کلاینت‌های سازگار وارد کنید.
""",
        parse_mode="HTML",
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )


# ------------------ extend test subscription ------------------


async def extend_test_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    service_name = "اشتراک تست"

    text = context.user_data.get("subscription_text", "")

    if "🆔️ نام سرویس:" in text:
        try:
            service_name = (
                text.split("🆔️ نام سرویس:")[1]
                .split("\n")[0]
                .strip()
                .replace("<b>", "")
                .replace("</b>", "")
            )
        except:
            pass

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "⬅️ بازگشت",
                    callback_data="back_to_subscription",
                )
            ],
            [
                InlineKeyboardButton(
                    "💎 خرید اشتراک",
                    callback_data="buy_subscription",
                )
            ],
        ]
    )

    await query.edit_message_text(
        f"""❌ <b>شما نمی‌توانید اشتراک تست را تمدید کنید!</b>

🆔️ نام اشتراک: <b>{service_name}</b>

🎁 این یک اشتراک تست رایگان است و قابلیت تمدید ندارد.

✅ لطفاً برای ادامه استفاده، یک اشتراک جدید خریداری کنید.""",
        parse_mode="HTML",
        reply_markup=keyboard,
    )


# ------------------ buy subscription callback ------------------


async def buy_subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    await query.message.reply_text("""💎 خرید اشتراک

🚧 این بخش در حال آماده‌سازی است.

به‌زودی امکان خرید اشتراک از طریق ربات فعال خواهد شد.

🙏 از صبر و همراهی شما متشکریم. ❤️""")


# ------------------ rename service callback ------------------


async def rename_service_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    service_id = query.data.replace("rename_", "").strip()

    context.user_data.pop("waiting_for_support", None)
    context.user_data.pop("contact_mode", None)
    context.user_data["waiting_for_service_name"] = True
    context.user_data["rename_service_id"] = service_id

    await query.message.reply_text(
        """✏️ نام جدید سرویس را ارسال کنید.

📝 مثال:
<code>SAJJAD-USA</code>

⚠️ شرایط:
• حداقل ۳ کاراکتر""",
        parse_mode="HTML",
    )


# ------------------ receive new service name ------------------


async def receive_new_service_name(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.user_data.get("waiting_for_service_name"):
        return

    if not update.message or not update.message.text:
        await update.effective_message.reply_text(
            "❌ لطفاً فقط نام جدید سرویس را به صورت متن ارسال کنید."
        )
        return

    custom_name = update.message.text.strip()

    service_id = context.user_data.get("rename_service_id")

    if not service_id:
        context.user_data["waiting_for_service_name"] = False
        await update.effective_message.reply_text("❌ شناسه سرویس پیدا نشد.")
        return

    if len(custom_name) < 3:
        await update.effective_message.reply_text(
            """❌ نام سرویس باید حداقل ۳ کاراکتر باشد.

لطفاً دوباره نام جدید را ارسال کنید."""
        )
        return

    new_name = f"TG-{update.effective_user.id}-{custom_name}"

    try:

        success = rename_service(service_id, new_name)

        if success:
            update_service_name(service_id, new_name)

    except Exception as e:

        context.user_data["waiting_for_service_name"] = False

        await update.effective_message.reply_text(
            f"""❌ خطا:

<code>{e}</code>""",
            parse_mode="HTML",
        )
        return

    if success:

        context.user_data["waiting_for_service_name"] = False
        context.user_data.pop("rename_service_id", None)

        context.user_data["service_name"] = new_name
        context.user_data["subscription_name"] = new_name

        await update.effective_message.reply_text(
            f"""✅ نام سرویس با موفقیت تغییر کرد.

🆕 نام جدید:
<b>{custom_name}</b>""",
            parse_mode="HTML",
        )

    else:

        await update.effective_message.reply_text("""❌ خطا در تغییر نام سرویس.

لطفاً دوباره نام جدید را ارسال کنید.""")


# ------------------ back to subscription ------------------


@membership_required
async def back_to_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    service_id = context.user_data.get("subscription_service_id")
    sub_link = context.user_data.get("subscription_sub_link")
    text = context.user_data.get("subscription_text")

    keyboard_buttons = [
        [
            InlineKeyboardButton(
                "📄 مشاهده کانفیگ‌ها",
                callback_data=f"show_configs_{service_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                "🔗 باز کردن لینک ساب",
                url=sub_link,
            ),
        ],
        [
            InlineKeyboardButton(
                "✏️ تغییر نام سرویس",
                callback_data=f"rename_{service_id}",
            ),
            InlineKeyboardButton(
                "🔄 تمدید اشتراک",
                callback_data=f"renew_{service_id}",
            ),
        ],
    ]

    if context.user_data.get("from_my_subscriptions", False):
        keyboard_buttons.append(
            [
                InlineKeyboardButton(
                    "⬅️ بازگشت",
                    callback_data="back_to_services",
                ),
            ]
        )

    keyboard = InlineKeyboardMarkup(keyboard_buttons)

    await query.edit_message_text(
        text=text,
        parse_mode="HTML",
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )


# ------------------ vpn test request ------------------


@membership_required
async def vpn_test_request(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user = query.from_user

    balance = get_balance(user.id)
    price = 5000

    if balance < price:

        shortage = price - balance

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "👥 دعوت دوستان",
                        callback_data="referral_menu",
                    )
                ]
            ]
        )

        await query.edit_message_text(
            f"""❌ اعتبار شما کافی نیست!

💰 هزینه اشتراک: {price:,} تومان
💳 اعتبار فعلی شما: {balance:,} تومان
📉 اعتبار کمبود: {shortage:,} تومان

✨ با دعوت دوستان اعتبار کسب کنید.""",
            reply_markup=keyboard,
        )

        return

    random_id = random.randint(100, 999)

    service_name = f"TG-{user.id}-TEST-{random_id}"
    username = service_name

    result = create_nahan_user(
        username=username,
        traffic_gb=1,
        expiry_days=30,
    )

    if not result:

        await query.edit_message_text(
            "❌ خطا در ساخت اشتراک. لطفاً بعداً دوباره تلاش کنید."
        )

        return

    sub_link = result["subscription_url"]
    service_id = result["service_id"]

    save_user_service(
        service_id=service_id,
        user_id=user.id,
        service_name=service_name,
        subscription_url=sub_link,
    )

    configs = get_vless_configs(sub_link)

    update_service_configs(service_id, configs)

    regions = []
    seen = set()

    for config in configs:
        if "#" not in config:
            continue

        region = config.split("#", 1)[1].split("|", 1)[0].strip()

        if region and region not in seen:
            seen.add(region)
            regions.append(region)

    region = "\n".join(regions) if regions else "🌐"

    update_service_region(service_id, region)

    update_service_region(service_id, region)

    deduct_balance(user.id, price)

    new_balance = get_balance(user.id)

    iran_now = datetime.utcnow() + timedelta(hours=3, minutes=30)
    expire = iran_now + timedelta(days=30)

    buy_date = jdatetime.datetime.fromgregorian(datetime=iran_now).strftime(
        "%Y/%m/%d - %H:%M"
    )

    expire_date = jdatetime.datetime.fromgregorian(datetime=expire).strftime(
        "%Y/%m/%d - %H:%M"
    )

    subscription_text = f"""<i>🎉 اشتراک تست شما با موفقیت ایجاد شد.</i>

💰 مبلغ کسر شده: <b>{price:,} تومان</b>
💳 اعتبار باقی‌مانده: <b>{new_balance:,} تومان</b>

🆔️ نام سرویس: <b>{service_name}</b>
📦 حجم: <b>1 GB</b>
⏳ مدت: <b>30 روز</b>
📅 تاریخ خرید: <b>{buy_date}</b>
🗓 تاریخ پایان: <b>{expire_date}</b>
👥 اتصال همزمان: <b>نامحدود</b>
🌍 ریجن:
 <b>{region}</b>

🔗 لینک ساب:
<code>{sub_link}</code>

📄 کانفیگ‌ها:
<b>برای مشاهده و کپی کانفیگ‌ها، روی دکمه «📄 مشاهده کانفیگ‌ها» بزنید.</b>

━━━━━━━━━━━━━━
<i>🤖 By: @{(await context.bot.get_me()).username}</i>

<b>در صورت بروز هرگونه مشکل، از طریق دکمه «💬 پشتیبانی» با ما در ارتباط باشید.</b>
"""

    context.user_data["subscription_text"] = subscription_text
    context.user_data["subscription_sub_link"] = sub_link
    context.user_data["subscription_service_id"] = service_id
    context.user_data["from_my_subscriptions"] = False
    context.user_data["service_id"] = service_id
    context.user_data["service_name"] = service_name
    context.user_data["subscription_name"] = service_name

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📄 مشاهده کانفیگ‌ها",
                    callback_data="show_configs",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔗 باز کردن لینک ساب",
                    url=sub_link,
                ),
            ],
            [
                InlineKeyboardButton(
                    "✏️ تغییر نام سرویس",
                    callback_data=f"rename_{service_id}",
                ),
                InlineKeyboardButton(
                    "🔄 تمدید اشتراک",
                    callback_data="extend_test_subscription",
                ),
            ],
        ]
    )

    await query.edit_message_text(
        text=subscription_text,
        reply_markup=keyboard,
        parse_mode="HTML",
    )


# ------------------ send config callback ------------------


async def send_config_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user_id = int(query.data.split("_")[-1])

    ADMIN_WAITING_FOR_SUB[query.from_user.id] = user_id

    await query.message.reply_text(
        "📎 مرحله ۱ از ۲\n\n" "لطفاً لینک Subscription را ارسال کنید."
    )


# ------------------ receive subscription ------------------


async def receive_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):

    admin_id = update.effective_user.id

    if admin_id not in ADMIN_WAITING_FOR_SUB:
        return

    sub_link = update.message.text

    user_id = ADMIN_WAITING_FOR_SUB.pop(admin_id)

    ADMIN_WAITING_FOR_CONFIG[admin_id] = {
        "user_id": user_id,
        "sub": sub_link,
    }

    await update.message.reply_text(
        "📄 مرحله ۲ از ۲\n\n" "حالا کانفیگ(ها) را ارسال کنید."
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

    except Exception:

        await query.message.reply_text("❌ ارسال پیام با خطا مواجه شد.")


# ------------------ receive vpn config ------------------


@membership_required
async def receive_vpn_config(update: Update, context: ContextTypes.DEFAULT_TYPE):

    admin_id = update.effective_user.id

    if admin_id not in ADMIN_WAITING_FOR_CONFIG:
        return

    data = ADMIN_WAITING_FOR_CONFIG.pop(admin_id)

    user_id = data["user_id"]
    subscription = data["sub"]

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
            text=f"""🎉 اشتراک تست شما آماده شد.

⚙️ نوع: کانفیگ
🟢 وضعیت: فعال
♾️ مدت: 30 روز
📦 حجم: ۵ گیگابایت
⚡ سرعت: بالا
🌐 ریجن:
 آمریکا 🇺🇸

🔗 لینک اشتراک:

<code>{subscription}</code>

💻 کانفیگ‌ها:

<code>{config_text}</code>

💬 اگر در اتصال یا استفاده از سرویس مشکلی داشتید، به پشتیبانی پیام دهید.""",
            parse_mode="HTML",
            reply_markup=keyboard,
        )

        await update.message.reply_text(
            "✅ لینک اشتراک و کانفیگ با موفقیت برای کاربر ارسال شد."
        )

    except Exception:

        await update.message.reply_text("❌ ارسال اطلاعات برای کاربر با خطا مواجه شد.")


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

    users = get_users()

    for user_id in users:

        try:

            await context.bot.send_message(
                chat_id=int(user_id),
                text=text,
            )

            success += 1

        except (Forbidden, BadRequest):

            failed += 1

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

    if admin_id in ADMIN_WAITING_FOR_SUB:
        await receive_subscription(update, context)
        return

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

    if update.callback_query:
        await update.callback_query.answer()
        message = update.callback_query.message
    else:
        message = update.message

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📱 V2RayNG",
                    callback_data="guide_v2rayng",
                ),
                InlineKeyboardButton(
                    "📱 NPV Tunnel",
                    callback_data="guide_npv",
                ),
            ],
            [
                InlineKeyboardButton(
                    "📱 Hiddify Next",
                    callback_data="guide_hiddify",
                ),
                InlineKeyboardButton(
                    "📱 Netobox",
                    callback_data="guide_netobox",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🍎 Streisand",
                    callback_data="guide_streisand",
                ),
                InlineKeyboardButton(
                    "🍎 FoXray",
                    callback_data="guide_foxray",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🍎 Shadowrocket",
                    callback_data="guide_shadowrocket",
                ),
            ],
        ]
    )

    text = """
📚 <i><b>آموزش اتصال</b></i>

<b>برای استفاده از کانفیگ‌های ربات، ابتدا یکی از برنامه‌های زیر را نصب کنید.
پیشنهاد ما <a href="https://play.google.com/store/apps/details?id=com.napsternetlabs.napsternetv">NPV Tunnel</a> هست.</b>

🤖 <b>اندروید (Android)</b>
🔹 <b>V2RayNG</b>
🔹 <a href="https://play.google.com/store/apps/details?id=com.napsternetlabs.napsternetv"><b>NPV Tunnel</b></a>
🔹 <a href="https://play.google.com/store/apps/details?id=app.hiddify.com"><b>Hiddify Next</b></a>
🔹 <b>Netobox</b>
🍎 <b>آیفون (iOS)</b>
🔹 <b>Streisand</b>
🔹 <a href="https://play.google.com/store/apps/details?id=com.github.foxray"><b>FoXray</b></a>
🔹 <a href="https://play.google.com/store/apps/details?id=com.v2cross.proxy"><b>Shadowrocket</b></a>

<b>پس از نصب برنامه موردنظر، از دکمه‌های زیر آموزش همان برنامه را انتخاب کنید.</b>
"""

    if update.callback_query:
        await message.edit_text(
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=keyboard,
        )
    else:
        await message.reply_text(
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=keyboard,
        )


# ------------------ guide v2rayng ------------------


@membership_required
async def guide_v2rayng(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "💬 ارتباط با پشتیبانی",
                    callback_data="contact_support",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔙 بازگشت",
                    callback_data="vpn_guide",
                ),
            ],
        ]
    )

    await query.edit_message_text(
        """
📚 <i>آموزش V2rayNG</i>

➕ افزودن لینک سابسکریپشن
🔹 برنامه <b>V2rayNG</b> را باز کنید.
🔹 روی علامت <b>➕</b> بالای صفحه بزنید.
🔹 اگر لینک را کپی کرده‌اید، گزینه
<b>Import Configs from Clipboard</b>
را انتخاب کنید.
🔹 یا وارد
<b>Subscription Group Setting</b>
شوید.
🔹 روی <b>➕</b> بزنید.
🔹 در قسمت <b>Remarks</b> یک نام دلخواه
(مثلاً <b>AMT V2Ray</b>) وارد کنید.
🔹 لینک سابسکریپشن را در قسمت <b>URL</b> قرار دهید.
🔹 روی <b>✔️</b> بزنید تا ذخیره شود.

🔄 بروزرسانی (Update)
✅ وارد صفحه اصلی شوید.
✅ از منوی بالا گزینه
<b>Update Subscription</b>
را انتخاب کنید.
✅ چند ثانیه صبر کنید تا سرورها دریافت شوند.

🟢 اتصال
1️⃣ یکی از سرورها را انتخاب کنید.
2️⃣ روی دکمه <b>V</b> پایین صفحه بزنید.
3️⃣ در اولین اتصال، اجازه VPN را تأیید کنید.
4️⃣ پس از اتصال، وضعیت باید روی <b>Connected</b> قرار بگیرد. ✅

<b>اگر مشکلی داشتید از طریق دکمه پشتیبانی با ما در ارتباط باشید.</b>
""",
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=keyboard,
    )


# ------------------ guide hiddify ------------------


@membership_required
async def guide_hiddify(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "💬 ارتباط با پشتیبانی",
                    callback_data="contact_support",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔙 بازگشت",
                    callback_data="vpn_guide",
                ),
            ],
        ]
    )

    await query.edit_message_text(
        """
📚 <i>آموزش Hiddify Next</i>

➕ افزودن لینک
🔹 برنامه را باز کنید.
🔹 روی <b>➕ Add Profile</b> بزنید.
🔹 گزینه <b>From Clipboard</b> یا <b>From URL</b> را انتخاب کنید.
🔹 لینک سابسکریپشن را وارد کنید.
🔹 روی <b>Save</b> بزنید.

🔄 بروزرسانی
🔄 وارد پروفایل شوید.
🔄 روی <b>Refresh</b> بزنید.
🔄 سرورها به‌صورت خودکار بروزرسانی می‌شوند.

🟢 اتصال
🟢 روی دکمه اتصال بزنید.
🟢 اجازه VPN را تأیید کنید.
🟢 چند ثانیه صبر کنید تا متصل شوید.

<b>اگر مشکلی داشتید از طریق دکمه پشتیبانی با ما در ارتباط باشید.</b>
""",
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=keyboard,
    )


# ------------------ guide netobox ------------------


@membership_required
async def guide_netobox(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "💬 ارتباط با پشتیبانی",
                    callback_data="contact_support",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔙 بازگشت",
                    callback_data="vpn_guide",
                ),
            ],
        ]
    )

    await query.edit_message_text(
        """
📚 <i>آموزش Nekobox</i>

➕ افزودن لینک
🔹 برنامه را باز کنید.
🔹 وارد <b>Profiles</b> شوید.
🔹 روی <b>➕</b> بزنید.
🔹 گزینه <b>Add Subscription</b> را انتخاب کنید.
🔹 لینک را وارد کنید.
🔹 ذخیره کنید. 💾

🔄 بروزرسانی
🔄 از منوی پروفایل روی <b>Update Subscription</b> بزنید.

🟢 اتصال
🟢 سرور موردنظر را انتخاب کرده و دکمه اتصال را لمس کنید.

<b>اگر مشکلی داشتید از طریق دکمه پشتیبانی با ما در ارتباط باشید.</b>
""",
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=keyboard,
    )


# ------------------ guide streisand ------------------


@membership_required
async def guide_streisand(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "💬 ارتباط با پشتیبانی",
                    callback_data="contact_support",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔙 بازگشت",
                    callback_data="vpn_guide",
                ),
            ],
        ]
    )

    await query.edit_message_text(
        """
📚 <i>آموزش Streisand</i>

➕ افزودن لینک
🔹 برنامه را باز کنید.
🔹 روی <b>➕</b> بزنید.
🔹 گزینه <b>Import from URL</b> را انتخاب کنید.
🔹 لینک سابسکریپشن را وارد کنید.
🔹 روی <b>Import</b> بزنید.

🔄 بروزرسانی
🔄 وارد پروفایل شوید.
🔄 روی <b>Update</b> یا <b>Refresh</b> بزنید.

🟢 اتصال
🟢 سرور دلخواه را انتخاب کرده و دکمه اتصال را لمس کنید.

<b>اگر مشکلی داشتید از طریق دکمه پشتیبانی با ما در ارتباط باشید.</b>
""",
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=keyboard,
    )


# ------------------ guide foxray ------------------


@membership_required
async def guide_foxray(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "💬 ارتباط با پشتیبانی",
                    callback_data="contact_support",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔙 بازگشت",
                    callback_data="vpn_guide",
                ),
            ],
        ]
    )

    await query.edit_message_text(
        """
📚 <i>آموزش FoXray</i>

➕ افزودن لینک
🔹 برنامه را باز کنید.
🔹 روی <b>➕</b> بزنید.
🔹 گزینه <b>Add Subscription</b> را انتخاب کنید.
🔹 لینک را وارد کنید.
🔹 ذخیره کنید. 💾

🔄 بروزرسانی
🔄 گزینه <b>Update Subscription</b> را انتخاب کنید.

🟢 اتصال
🟢 سرور موردنظر را انتخاب کرده و روی <b>Connect</b> بزنید.

<b>اگر مشکلی داشتید از طریق دکمه پشتیبانی با ما در ارتباط باشید.</b>
""",
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=keyboard,
    )


# ------------------ guide shadowrocket ------------------


@membership_required
async def guide_shadowrocket(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "💬 ارتباط با پشتیبانی",
                    callback_data="contact_support",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔙 بازگشت",
                    callback_data="vpn_guide",
                ),
            ],
        ]
    )

    await query.edit_message_text(
        """
📚 <i>آموزش Shadowrocket</i>

➕ افزودن لینک
🔹 برنامه را باز کنید.
🔹 روی <b>➕</b> بالای صفحه بزنید.
🔹 نوع را روی <b>Subscribe</b> قرار دهید.
🔹 یک نام دلخواه وارد کنید.
🔹 لینک سابسکریپشن را در قسمت <b>URL</b> وارد کنید.
🔹 روی <b>Done</b> بزنید.

🔄 بروزرسانی
🔄 روی سابسکریپشن نگه دارید یا گزینه <b>Update</b> را انتخاب کنید.

🟢 اتصال
🟢 سوئیچ بالای برنامه را روشن کنید.
🟢 در اولین اتصال، اجازه <b>VPN</b> را تأیید کنید.

<b>اگر مشکلی داشتید از طریق دکمه پشتیبانی با ما در ارتباط باشید.</b>
""",
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=keyboard,
    )


# ------------------ guide npv ------------------


@membership_required
async def guide_npv(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "💬 ارتباط با پشتیبانی",
                    callback_data="contact_support",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔙 بازگشت",
                    callback_data="vpn_guide",
                ),
            ],
        ]
    )

    await query.edit_message_text(
        """
📚 <i>آموزش NPV Tunnel</i>

1️⃣ کانفیگی که ربات برایتان ارسال کرده را کپی کنید.
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

<b>اگر مشکلی داشتید از طریق دکمه پشتیبانی با ما در ارتباط باشید.</b>
""",
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=keyboard,
    )


# ------------------ forward to admin ------------------


@membership_required
async def forward_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if context.user_data.get("waiting_for_service_name"):
        return

    if update.effective_user.id == ADMIN_ID:
        return

    if not context.user_data.get("waiting_for_support"):
        return

    user = update.effective_user

    caption = (
        f"📩 پیام جدید\n\n"
        f"👤 نام: {user.full_name}\n"
        f"🆔 آیدی عددی: {user.id}\n"
        f"📎 برای پاسخ روی همین پیام ریپلای کن."
    )

    try:

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=caption,
        )

        await context.bot.forward_message(
            chat_id=ADMIN_ID,
            from_chat_id=update.effective_chat.id,
            message_id=update.effective_message.message_id,
        )

        await update.effective_message.reply_text("✅ پیام شما برای پشتیبانی ارسال شد.")

        context.user_data["waiting_for_support"] = False
        context.user_data.pop("contact_mode", None)

    except Exception:

        await update.effective_message.reply_text(
            "❌ خطا در ارسال پیام. دوباره تلاش کنید."
        )


# ------------------ ADMIN REPLY ------------------

import re
import traceback


async def admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        return

    if not update.message.reply_to_message:
        return

    try:
        reply = update.message.reply_to_message

        if not reply.text:
            return

        match = re.search(r"🆔\s*آیدی عددی:\s*(\d+)", reply.text)

        if not match:
            return

        user_id = int(match.group(1))

        await context.bot.send_message(
            chat_id=user_id,
            text=("📬 <b>پاسخ مدیر</b>\n\n" f"{update.message.text}"),
            parse_mode="HTML",
        )

        await update.message.reply_text("✅ پاسخ با موفقیت برای کاربر ارسال شد.")

    except Exception:
        await update.message.reply_text(
            "❌ هنگام ارسال پاسخ خطایی رخ داد. خطا داخل ترمینال چاپ شد."
        )


# ------------------ contact support callback ------------------


@membership_required
async def contact_support_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    context.user_data["waiting_for_support"] = True
    context.user_data.pop("waiting_for_service_name", None)

    await query.message.reply_text(
        """💬 ارتباط با پشتیبانی

پیام خود را ارسال کنید.

پیام شما مستقیماً برای ادمین ارسال می‌شود و پاسخ نیز از طریق همین ربات برایتان ارسال خواهد شد."""
    )


# ------------------ contact me ------------------


@membership_required
async def contact_me(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data["contact_mode"] = True
    context.user_data.pop("waiting_for_service_name", None)
    context.user_data.pop("rename_service_id", None)
    context.user_data["waiting_for_support"] = True

    # اگر قبلاً در حالت تغییر نام سرویس بوده، لغوش کن
    context.user_data.pop("waiting_for_service_name", None)

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


# ------------------- referral menu ------------------


@membership_required
async def referral_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.callback_query:
        await update.callback_query.answer()
        user_id = update.callback_query.from_user.id
    else:
        user_id = update.effective_user.id

    # موجودی واقعی
    balance = get_balance(user_id)

    # تعداد زیرمجموعه‌ها
    referrals_count = get_referrals_count(user_id)

    # لیست زیرمجموعه‌ها
    referrals = get_referrals(user_id)

    bot_username = (await context.bot.get_me()).username

    ref_link = f"https://t.me/{bot_username}?start={user_id}"

    share_text = quote(f"""👋 سلام!

من از این ربات استفاده می‌کنم و واقعاً از امکاناتش راضی‌ام. 🚀

اگر دوست داشتی، تو هم یه سر بهش بزن 👇

{ref_link}
""")

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📤 اشتراک‌گذاری لینک دعوت",
                    url=f"https://t.me/share/url?url=&text={share_text}",
                )
            ]
        ]
    )

    # ساخت تاریخچه زیرمجموعه‌ها
    if referrals:

        history = "\n━━━━━━━━━━━━━━\n👥 <b>آخرین زیرمجموعه‌ها</b>\n\n"

        for row in referrals[:10]:

            name = row["full_name"] or "بدون نام"

            status = "🟢" if row["reward_paid"] else "🟡"

            history += f"{status} {name}\n"

    else:

        history = "\n━━━━━━━━━━━━━━\n👥 هنوز هیچ زیرمجموعه‌ای ثبت نشده است."

    text = f"""👥 <b>پنل زیرمجموعه گیری</b>

💳 اعتبار:
<b>{balance:,} تومان</b>

👤 زیرمجموعه‌های فعال:
<b>{referrals_count} نفر</b>

🔗 <b>لینک دعوت اختصاصی:</b>

<code>{ref_link}</code>

<i>💬 لینک بالا را برای دوستان خود ارسال کنید.
پس از عضویت آن‌ها در کانال و تأیید عضویت، به ازای هر نفر 10,000 تومان اعتبار دریافت خواهید کرد.</i>{history}
"""

    if update.callback_query:
        await update.callback_query.message.reply_text(
            text,
            parse_mode="HTML",
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )
    else:
        await update.message.reply_text(
            text,
            parse_mode="HTML",
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )


# ------------------ profile ------------------


@membership_required
async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    balance = get_balance(user.id)

    referrals = get_referrals_count(user.id)

    earnings = get_referral_earnings(user.id)

    join_date = get_join_date(user.id)

    if join_date:

        dt = datetime.strptime(join_date, "%Y-%m-%d %H:%M:%S")

        iran_time = dt + timedelta(hours=3, minutes=30)

        jdt = jdatetime.datetime.fromgregorian(datetime=iran_time)

        join_text = jdt.strftime("%Y/%m/%d - %H:%M")

    else:

        join_text = "نامشخص"

    await update.message.reply_text(
        f"""<b>🥇 پروفایل شما</b>

🆔 شناسه: <code>{user.id}</code>
👤 نام: <b>{user.full_name}</b>
💳 موجودی: <b>{balance:,} تومان</b>
👥 تعداد دعوت: <b>{referrals}</b>
💰 مجموع درآمد از دعوت: <b>{earnings:,} تومان</b>
📅 تاریخ عضویت: <b>{join_text}</b>
""",
        parse_mode="HTML",
    )


# ------------------ my subscriptions ------------------


@membership_required
async def my_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE):

    services = get_user_services(update.effective_user.id)

    buttons = []

    for service_id, service_name, subscription_url in services:

        display_name = service_name

        prefix = f"TG-{update.effective_user.id}-"
        if display_name.startswith(prefix):
            display_name = display_name[len(prefix) :]

        buttons.append(
            [
                InlineKeyboardButton(
                    display_name,
                    callback_data=f"subscription_{service_id}",
                )
            ]
        )

    if not buttons:

        buttons.append(
            [
                InlineKeyboardButton(
                    "❌ سرویسی پیدا نشد",
                    callback_data="no_subscription",
                )
            ]
        )

    keyboard = InlineKeyboardMarkup(buttons)

    await update.message.reply_text(
        """📦 <b>اشتراک‌های فعال من</b>

لیست سرویس‌های شما آماده است.
برای دیدن جزئیات، روی سرویس موردنظر بزنید.""",
        parse_mode="HTML",
        reply_markup=keyboard,
    )


# ------------------ subscription details ------------------


@membership_required
async def subscription_details(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    service_id = query.data.replace("subscription_", "")

    service = get_service_by_id(service_id)

    if not service:
        await query.edit_message_text("❌ سرویس پیدا نشد.")
        return

    # اطلاعات سرویس
    name = service.get("name", "-")

    prefix = f"TG-{query.from_user.id}-"
    if name.startswith(prefix):
        name = name[len(prefix) :]

    status = "فعال ✅" if service.get("status") == "active" else "غیرفعال ❌"

    usage = service.get("usage", {})

    used = usage.get("total", 0) / (1024**3)
    total = usage.get("limit", 0) / (1024**3)
    remain = max(total - used, 0)

    expiry = service.get("expiryMs")
    created = service.get("createdAt")

    created_dt = datetime.fromtimestamp(created / 1000)
    expiry_dt = datetime.fromtimestamp(expiry / 1000)

    created_shamsi = jdatetime.datetime.fromgregorian(datetime=created_dt).strftime(
        "%Y/%m/%d - %H:%M"
    )

    expiry_shamsi = jdatetime.datetime.fromgregorian(datetime=expiry_dt).strftime(
        "%Y/%m/%d - %H:%M"
    )

    days_left = max((expiry_dt - datetime.now()).days, 0)

    conn = service.get("connLimit")
    conn_text = "نامحدود" if conn in (None, 0) else str(conn)

    sub_link = get_subscription_by_service(service_id)
    region = get_service_region(service_id)

    text = f"""<i>📦 اطلاعات سرویس</i>

🆔️ نام سرویس: <b>{name}</b>
📅 تاریخ خرید: <b>{created_shamsi}</b>
🗓 تاریخ پایان: <b>{expiry_shamsi}</b>

🔮 وضعیت: <b>{status}</b>

📦 حجم کل: <b>{total:.2f} GB</b>
📤 مصرف شده: <b>{used:.2f} GB</b>
📥 حجم باقی‌مانده: <b>{remain:.2f} GB</b>
⏳ زمان باقی‌مانده: <b>{days_left} روز</b>
👥 اتصال همزمان: <b>{conn_text}</b>
🌍 ریجن:
 <b>{region}</b>

🔗 لینک ساب:
<code>{sub_link}</code>

📄 کانفیگ‌ها:
<b>برای مشاهده و کپی کانفیگ‌ها، روی دکمه «📄 مشاهده کانفیگ‌ها» بزنید.</b>

━━━━━━━━━━━━━━
<i>🤖 By: @{(await context.bot.get_me()).username}</i>

<b>در صورت بروز هرگونه مشکل، از طریق دکمه «💬 ارتباط با پشتیبانی» با ما در ارتباط باشید.</b>
"""

    context.user_data["subscription_text"] = text
    context.user_data["subscription_service_id"] = service_id
    context.user_data["from_my_subscriptions"] = True
    context.user_data["subscription_sub_link"] = sub_link
    context.user_data["subscription_name"] = name
    context.user_data["service_id"] = service_id
    context.user_data["service_name"] = name

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📄 مشاهده کانفیگ‌ها",
                    callback_data=f"show_configs_{service_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔗 باز کردن لینک ساب",
                    url=sub_link if sub_link.startswith("http") else "https://t.me",
                ),
            ],
            [
                InlineKeyboardButton(
                    "✏️ تغییر نام سرویس",
                    callback_data=f"rename_{service_id}",
                ),
                InlineKeyboardButton(
                    "🔄 تمدید اشتراک",
                    callback_data=f"renew_{service_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "⬅️ بازگشت",
                    callback_data="back_to_services",
                ),
            ],
        ]
    )

    await query.edit_message_text(
        text=text,
        parse_mode="HTML",
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )


# ------------------ check join callback ------------------


async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if await check_membership(user_id, context):

        # ---------------- Referral Reward ----------------

        inviter_id = get_inviter(user_id)

        if inviter_id and not reward_already_paid(user_id):

            add_balance(inviter_id, 10000)

            mark_reward_paid(user_id)

            try:
                await context.bot.send_message(
                    chat_id=inviter_id,
                    text="""
🎉 تبریک!

یک نفر با لینک دعوت شما عضو کانال شد. 🥳

💳 مبلغ 10,000 تومان به اعتبار حساب شما اضافه شد.
""",
                )
            except Exception:
                pass

        # -----------------------------------------------

        await query.message.delete()

        if query.message.chat.type == "private":

            await context.bot.send_message(
                chat_id=user_id,
                text="""✅ عضویت شما تایید شد.

🎉 به ربات خوش اومدید

🔮 برای ادامه، از دکمه‌های زیر استفاده کنید:""",
                reply_markup=MAIN_KEYBOARD,
            )

        else:

            await context.bot.send_message(
                chat_id=user_id,
                text="""✅ عضویت شما تایید شد.

🎉 به ربات خوش اومدید

🔮 برای ادامه، از منوی ربات استفاده کنید.""",
            )

    else:

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

    total_users = get_users_count()

    await update.message.reply_text(
        f"""
📊 <b>آمار ربات</b>

━━━━━━━━━━━━━━

👥 تعداد کاربران:
<b>{total_users}</b>

🗄 پایگاه داده:
<code>SQLite</code>

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

    total_users = get_users_count()

    await query.edit_message_text(
        f"""
📊 <b>آمار ربات</b>

━━━━━━━━━━━━━━

👥 تعداد کاربران:
<b>{total_users}</b>

🗄 پایگاه داده:
<code>SQLite</code>

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


# ------------------- test command ------------------


async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status, result = create_nahan_user()

    await update.message.reply_text(f"Status: {status}\n\n{result}")


# ------------------ text router ------------------


async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):

    # اگر منتظر تغییر نام سرویس است
    if context.user_data.get("waiting_for_service_name"):
        return await receive_new_service_name(update, context)

    # اگر منتظر پیام پشتیبانی است
    elif context.user_data.get("waiting_for_support"):
        return await forward_to_admin(update, context)

    # هیچ حالت خاصی فعال نیست
    return


# ------------------ back to services ------------------


async def back_to_services(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    services = get_user_services(update.effective_user.id)

    buttons = []

    for service_id, service_name, subscription_url in services:

        display_name = service_name

        prefix = f"TG-{update.effective_user.id}-"
        if display_name.startswith(prefix):
            display_name = display_name[len(prefix) :]

        buttons.append(
            [
                InlineKeyboardButton(
                    display_name,
                    callback_data=f"subscription_{service_id}",
                )
            ]
        )

    if not buttons:
        buttons.append(
            [
                InlineKeyboardButton(
                    "❌ سرویسی پیدا نشد",
                    callback_data="no_subscription",
                )
            ]
        )

    keyboard = InlineKeyboardMarkup(buttons)

    await query.edit_message_text(
        """📦 <b>اشتراک‌های فعال من</b>

لیست سرویس‌های شما آماده است.
برای دیدن جزئیات، روی سرویس موردنظر بزنید.""",
        parse_mode="HTML",
        reply_markup=keyboard,
    )


# ------------------ set news command ------------------


@admin_only
async def set_news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    # اگر داخل گروه بود، کیبورد اصلی حذف شود
    if update.effective_chat.type != "private":

        await update.message.reply_text(
            "🛠 حالت ثبت خبر فعال شد.",
            reply_markup=ReplyKeyboardRemove(),
        )

    context.user_data["waiting_news_key"] = "main"

    await update.message.reply_text("📰 متن خبر اصلی را ارسال کنید.")


# ------------------ set prediction command ------------------


@admin_only
async def set_prediction_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data["waiting_news_key"] = "prediction"

    await update.message.reply_text("🔮 متن بخش «پیش‌بینی و احتمالات» را ارسال کنید.")


# ------------------ set persons command ------------------


@admin_only
async def set_persons_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data["waiting_news_key"] = "persons"

    await update.message.reply_text("🎯 متن بخش «محورها و اشخاص» را ارسال کنید.")


# ------------------ set market command ------------------


@admin_only
async def set_market_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data["waiting_news_key"] = "market"

    await update.message.reply_text("📈 متن بخش «بازار و اقتصاد (زنده)» را ارسال کنید.")


# ------------------ set assessment command ------------------


@admin_only
async def set_assessment_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data["waiting_news_key"] = "assessment"

    await update.message.reply_text("🛡 متن بخش «ارزیابی و آسیب‌پذیری» را ارسال کنید.")


# ------------------ receive news ------------------


async def receive_news(update: Update, context: ContextTypes.DEFAULT_TYPE):

    key = context.user_data.get("waiting_news_key")

    if key is None:
        return

    if not update.message:
        return

    # دریافت متن همراه با فرمت‌های HTML (Bold, Italic, Underline, Link و...)
    text = update.message.text_html

    if not text or not text.strip():
        await update.message.reply_text("❌ لطفاً فقط متن خبر را ارسال کنید.")
        return

    # ذخیره در دیتابیس
    set_news(key, text)

    # خروج از حالت انتظار
    context.user_data.pop("waiting_news_key", None)

    await update.message.reply_text("✅ خبر با موفقیت ذخیره شد.")


# ------------------ strategic news ------------------


@membership_required
async def strategic_news(update: Update, context: ContextTypes.DEFAULT_TYPE):

    news = get_news("main")

    if not news:
        news = "❌ هنوز هیچ خبر راهبردی ثبت نشده است."

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🔮 پیش‌بینی و احتمالات",
                    callback_data="news_prediction",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🎯 محورها و اشخاص",
                    callback_data="news_persons",
                ),
            ],
            [
                InlineKeyboardButton(
                    "📈 بازار و اقتصاد (زنده)",
                    callback_data="news_market",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🛡 ارزیابی و آسیب‌پذیری",
                    callback_data="news_assessment",
                ),
            ],
        ]
    )

    await update.message.reply_text(
        news,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=keyboard,
    )


# ------------------ news prediction callback ------------------


async def news_prediction_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.callback_query.answer()

    news = get_news("prediction")

    if not news:
        news = "❌ هنوز متنی برای این بخش ثبت نشده است."

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🏠 بازگشت به داشبورد اصلی",
                    callback_data="back_to_dashboard",
                ),
            ]
        ]
    )

    await update.callback_query.edit_message_text(
        text=news,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=keyboard,
    )


# ------------------ news persons callback ------------------


async def news_persons_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.callback_query.answer()

    news = get_news("persons")

    if not news:
        news = "❌ هنوز متنی برای این بخش ثبت نشده است."

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🏠 بازگشت به داشبورد اصلی",
                    callback_data="back_to_dashboard",
                ),
            ]
        ]
    )

    await update.callback_query.edit_message_text(
        text=news,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=keyboard,
    )


# ------------------ news market callback ------------------

from datetime import datetime
from zoneinfo import ZoneInfo


async def news_market_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.callback_query.answer()

    news = get_news("market")

    if isinstance(news, dict):
        news_text = news.get("content") or "❌ هنوز متنی برای این بخش ثبت نشده است."
    else:
        news_text = news or "❌ هنوز متنی برای این بخش ثبت نشده است."

    prices = get_market_prices()

    # زمان تهران
    now = datetime.now(ZoneInfo("Asia/Tehran"))

    # تبدیل به شمسی
    jnow = jdatetime.datetime.fromgregorian(datetime=now)

    market_text = f"""
{news_text}

➖➖➖➖➖➖➖➖
<b>📊 قیمت‌های زنده بازار:</b>

┓ <b>💵 دلار آزاد ( ایران ):</b> {prices["usd"]} تومان
┫ <b>🥇 طلای 18 عیار:</b> {prices["gold"]} تومان
┫ <b>🪙 بیت‌کوین:</b> ${prices["bitcoin"]}
┛ <b>💎 تون‌ ( گرام ):</b> ${prices["ton"]}

<i>🕑 {jnow.strftime("%Y/%m/%d • %H:%M:%S")} (Tehran)</i>
"""

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🏠 بازگشت به داشبورد اصلی",
                    callback_data="back_to_dashboard",
                ),
            ]
        ]
    )

    await update.callback_query.edit_message_text(
        text=market_text,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=keyboard,
    )


# ------------------ news assessment callback ------------------


async def news_assessment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.callback_query.answer()

    news = get_news("assessment")

    if not news:
        news = "❌ هنوز متنی برای این بخش ثبت نشده است."

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🏠 بازگشت به داشبورد اصلی",
                    callback_data="back_to_dashboard",
                ),
            ]
        ]
    )

    await update.callback_query.edit_message_text(
        text=news,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=keyboard,
    )


# ------------------ back news main ------------------


async def back_news_main(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.callback_query.answer()

    news = get_news("main")

    content = (
        news["content"]
        if news and news["content"]
        else "❌ هنوز هیچ خبر راهبردی ثبت نشده است."
    )

    photo = news["photo"] if news else None

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🔮 پیش‌بینی و احتمالات",
                    callback_data="news_prediction",
                )
            ],
            [
                InlineKeyboardButton(
                    "🎯 محورها و اشخاص",
                    callback_data="news_persons",
                )
            ],
            [
                InlineKeyboardButton(
                    "📈 بازار و اقتصاد (زنده)",
                    callback_data="news_market",
                )
            ],
            [
                InlineKeyboardButton(
                    "🛡 ارزیابی و آسیب‌پذیری",
                    callback_data="news_assessment",
                )
            ],
        ]
    )

    if photo and update.callback_query.message.photo:

        await update.callback_query.edit_message_caption(
            caption=content,
            parse_mode="HTML",
            reply_markup=keyboard,
        )

    else:

        await update.callback_query.edit_message_text(
            text=content,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=keyboard,
        )


# ------------------ set bot commands ------------------


from telegram import BotCommand, BotCommandScopeChat, BotCommandScopeDefault


async def set_bot_commands(application):

    # حذف همه دستورات برای کاربران عادی (PV)
    await application.bot.set_my_commands(
        [],
        scope=BotCommandScopeDefault(),
    )

    # دستورات فقط برای گروه ادمین
    admin_commands = [
        BotCommand("start", "شروع ربات"),
        BotCommand("setnews", "ثبت خبر اصلی"),
        BotCommand("setprediction", "ثبت پیش‌بینی و احتمالات"),
        BotCommand("setpersons", "ثبت محورها و اشخاص"),
        BotCommand("setmarket", "ثبت بازار و اقتصاد"),
        BotCommand("setassessment", "ثبت ارزیابی و آسیب‌پذیری"),
    ]

    await application.bot.set_my_commands(
        admin_commands,
        scope=BotCommandScopeChat(chat_id=-1004269590368),
    )


# ------------------ chatid command ------------------


@admin_only
async def chatid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Chat ID:\n<code>{update.effective_chat.id}</code>",
        parse_mode="HTML",
    )


# ------------------ back to dashboard ------------------


async def back_to_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.callback_query.answer()

    news = get_news("main")

    if not news:
        news = "❌ هنوز هیچ خبر راهبردی ثبت نشده است."

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🔮 پیش‌بینی و احتمالات",
                    callback_data="news_prediction",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🎯 محورها و اشخاص",
                    callback_data="news_persons",
                ),
            ],
            [
                InlineKeyboardButton(
                    "📈 بازار و اقتصاد (زنده)",
                    callback_data="news_market",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🛡 ارزیابی و آسیب‌پذیری",
                    callback_data="news_assessment",
                ),
            ],
        ]
    )

    await update.callback_query.edit_message_text(
        text=news,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=keyboard,
    )


# ---------------------------------------------- HANDLERS -----------------------------------------


def get_handlers():

    return [
        # ---------------- Commands ----------------
        CommandHandler("start", start),
        CommandHandler("admin", admin_panel),
        CommandHandler("stats", stats),
        CommandHandler("test", test_command),
        CommandHandler(
            "setnews",
            set_news_command,
        ),
        CommandHandler(
            "setprediction",
            set_prediction_command,
        ),
        CommandHandler(
            "setpersons",
            set_persons_command,
        ),
        CommandHandler(
            "setmarket",
            set_market_command,
        ),
        CommandHandler(
            "setassessment",
            set_assessment_command,
        ),
        CommandHandler("chatid", chatid_command),
        # ---------------- Reply Keyboard ----------------
        MessageHandler(filters.Regex("^👨‍💻 سازنده ربات$"), about_me),
        MessageHandler(filters.Regex("^🛠 خدمات$"), services),
        MessageHandler(filters.Regex("^🔙 بازگشت$"), back_to_main),
        MessageHandler(filters.Regex("^🔐 کانفیگ VPN$"), vpn_menu),
        MessageHandler(filters.Regex("^🎁 اشتراک تست$"), vpn_test),
        MessageHandler(filters.Regex("^💎 خرید اشتراک$"), buy_vpn),
        MessageHandler(filters.Regex("^👥 زیرمجموعه گیری$"), referral_menu),
        MessageHandler(
            filters.Regex("^🛰️ داشبورد اخبار راهبردی$"),
            strategic_news,
        ),
        MessageHandler(filters.Regex("^📚 آموزش اتصال$"), vpn_guide_callback),
        MessageHandler(filters.Regex("^👤 پروفایل$"), profile),
        MessageHandler(filters.Regex("^📦 اشتراک‌های من$"), my_subscriptions),
        MessageHandler(filters.Regex("^💬 ارتباط با پشتیبانی$"), contact_me),
        # ---------------- CallbackQuery ----------------
        CallbackQueryHandler(check_join_callback, pattern="^check_join$"),
        CallbackQueryHandler(vpn_test_request, pattern="^vpn_test_request$"),
        CallbackQueryHandler(show_configs, pattern=r"^show_configs"),
        CallbackQueryHandler(back_to_subscription, pattern="^back_to_subscription$"),
        CallbackQueryHandler(subscription_details, pattern="^subscription_"),
        CallbackQueryHandler(rename_service_callback, pattern=r"^rename_.+"),
        CallbackQueryHandler(extend_test_subscription, pattern="^renew_"),
        CallbackQueryHandler(
            extend_test_subscription,
            pattern="^extend_test_subscription$",
        ),
        CallbackQueryHandler(
            buy_subscription_callback,
            pattern="^buy_subscription$",
        ),
        CallbackQueryHandler(back_to_services, pattern="^back_to_services$"),
        CallbackQueryHandler(buy_vpn_callback, pattern="^buy_vpn$"),
        CallbackQueryHandler(referral_menu, pattern="^referral_menu$"),
        CallbackQueryHandler(vpn_guide_callback, pattern="^vpn_guide$"),
        CallbackQueryHandler(
            guide_v2rayng,
            pattern="^guide_v2rayng$",
        ),
        CallbackQueryHandler(
            guide_hiddify,
            pattern="^guide_hiddify$",
        ),
        CallbackQueryHandler(
            guide_netobox,
            pattern="^guide_netobox$",
        ),
        CallbackQueryHandler(
            guide_streisand,
            pattern="^guide_streisand$",
        ),
        CallbackQueryHandler(
            guide_foxray,
            pattern="^guide_foxray$",
        ),
        CallbackQueryHandler(
            guide_shadowrocket,
            pattern="^guide_shadowrocket$",
        ),
        CallbackQueryHandler(
            guide_npv,
            pattern="^guide_npv$",
        ),
        CallbackQueryHandler(send_config_callback, pattern="^send_config_"),
        CallbackQueryHandler(
            already_received_callback,
            pattern="^already_received_",
        ),
        CallbackQueryHandler(
            contact_support_callback,
            pattern="^contact_support$",
        ),
        CallbackQueryHandler(admin_stats_callback, pattern="^admin_stats$"),
        CallbackQueryHandler(
            admin_broadcast_callback,
            pattern="^admin_broadcast$",
        ),
        CallbackQueryHandler(
            news_prediction_callback,
            pattern="^news_prediction$",
        ),
        CallbackQueryHandler(
            news_persons_callback,
            pattern="^news_persons$",
        ),
        CallbackQueryHandler(
            news_market_callback,
            pattern="^news_market$",
        ),
        CallbackQueryHandler(
            news_assessment_callback,
            pattern="^news_assessment$",
        ),
        CallbackQueryHandler(
            back_news_main,
            pattern="^back_news_main$",
        ),
        CallbackQueryHandler(
            back_to_dashboard,
            pattern="^back_to_dashboard$",
        ),
        # ---------------- Admin ----------------
        MessageHandler(
            filters.User(ADMIN_ID) & filters.REPLY & ~filters.COMMAND,
            admin_reply,
        ),
        MessageHandler(
            filters.User(ADMIN_ID) & (filters.TEXT | filters.PHOTO) & ~filters.COMMAND,
            receive_news,
        ),
        MessageHandler(
            filters.User(ADMIN_ID) & filters.TEXT & ~filters.COMMAND,
            admin_text_router,
        ),
        # ---------------- Text Router ----------------
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_router,
            block=False,
        ),
    ]
