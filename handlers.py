from datetime import datetime, timedelta

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

import time
import random
import requests
import base64
import feedparser
from telegram.error import Forbidden, BadRequest
import requests
from deep_translator import GoogleTranslator
from functools import wraps
from database import add_user, get_users, get_users_count
from database import save_referral
from database import get_referrals_count
from database import save_referral, has_referral
from database import (
    get_inviter,
    reward_already_paid,
    mark_reward_paid,
    add_balance,
)
from database import get_balance, deduct_balance
from database import get_referrals
from database import get_join_date
from database import get_referral_earnings
from database import set_last_subscription, get_last_subscription
from urllib.parse import quote
from nahan_api import create_nahan_user
from nahan_api import rename_service
from nahan_api import (
    get_user_services,
    get_service_by_id,
    get_service_configs,
)
from nahan_api import test_patch_user, test_api_root
import jdatetime
from datetime import datetime, timedelta

ADMIN_WAITING_FOR_CONFIG = {}
ADMIN_WAITING_FOR_BROADCAST = set()
ADMIN_WAITING_FOR_SUB = {}

CHANNEL_USERNAME = "@SADSSCS"
CHANNEL_LINK = "https://t.me/SADSSCS"


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
        ["🌍 اخبار روز", "🔐 کانفیگ VPN"],
        ["🔙 بازگشت"],
    ],
    resize_keyboard=True,
)

VPN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🎁 اشتراک تست", "💎 خرید اشتراک"],
        ["📦 اشتراک‌های من", "👥 زیرمجموعه گیری"],
        ["📚 آموزش اتصال"],
        ["🔙 بازگشت"],
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

            if inviter_id != user_id and not has_referral(user_id):
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

    await update.message.reply_text(
        "🎉 به ربات خوش آمدید.",
        reply_markup=MAIN_KEYBOARD,
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


# ------------------ back to nenu ------------------


@membership_required
async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "به منوی اصلی بازگشتید.", reply_markup=MAIN_KEYBOARD
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


# ------------------ get first config ------------------


def get_vless_configs(subscription_url):

    try:

        r = requests.get(subscription_url, timeout=20)

        if r.status_code != 200:
            return []

        text = r.text.strip()

        try:
            decoded = base64.b64decode(text).decode("utf-8")
        except Exception:
            decoded = text

        configs = []
        seen = set()

        for line in decoded.splitlines():

            line = line.strip()

            if not line.lower().startswith("vless://"):
                continue

            if line in seen:
                continue

            seen.add(line)
            configs.append(line)

        return configs

    except Exception:
        return []


# ------------------ show configs ------------------


async def show_configs(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer(
        "⏳ در حال دریافت کانفیگ‌ها از پنل...",
        show_alert=False,
    )

    # اگر از صفحه اشتراک‌ها آمده باشد
    if query.data.startswith("show_configs_"):

        sub_link = context.user_data.get("subscription_sub_link")

    else:
        # اگر از پیام ساخت اشتراک آمده باشد
        sub_link = get_last_subscription(query.from_user.id)

    if not sub_link:

        await query.answer(
            "❌ اشتراکی برای شما پیدا نشد.",
            show_alert=True,
        )
        return

    configs = get_vless_configs(sub_link)

    if not configs:

        await query.answer(
            "❌ کانفیگی برای نمایش پیدا نشد.",
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

    context.user_data["waiting_for_service_name"] = True

    await query.message.reply_text("""✏️ نام جدید سرویس را ارسال کنید.

مثال:

SAJJAD-USA

❌ فقط از حروف انگلیسی، عدد و - استفاده کنید.""")


# ------------------ receive new service name ------------------


async def receive_new_service_name(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.user_data.get("waiting_for_service_name"):
        return

    context.user_data["waiting_for_service_name"] = False

    new_name = update.message.text.strip()

    old_name = context.user_data.get("service_name")

    if not old_name:
        await update.message.reply_text("❌ نام سرویس پیدا نشد.")
        return

    if rename_service(old_name, new_name):

        context.user_data["service_name"] = new_name

        await update.message.reply_text(
            f"✅ نام سرویس با موفقیت تغییر کرد.\n\n🆕 {new_name}"
        )

    else:

        await update.message.reply_text("❌ خطا در تغییر نام سرویس.")


# ------------------ back to subscription ------------------


@membership_required
async def back_to_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    service_id = context.user_data.get("subscription_service_id")
    sub_link = context.user_data.get("subscription_sub_link")
    text = context.user_data.get("subscription_text")

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
                    url=sub_link,
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔄 تمدید اشتراک",
                    callback_data=f"renew_{service_id}",
                ),
                InlineKeyboardButton(
                    "✏️ تغییر نام سرویس",
                    callback_data=f"rename_{service_id}",
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


# ------------------ vpn test request ------------------


@membership_required
async def vpn_test_request(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user = query.from_user

    balance = get_balance(user.id)
    price = 5000

    # اعتبار کافی نیست
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

    # ساخت نام سرویس
    random_id = random.randint(100, 999)

    service_name = f"TG-{user.id}-TEST-{random_id}"

    username = service_name

    # ساخت اشتراک
    sub_link = create_nahan_user(
        username=username,
        traffic_gb=1,
        expiry_days=30,
    )

    context.user_data["service_name"] = username

    if not sub_link:

        await query.edit_message_text(
            "❌ خطا در ساخت اشتراک. لطفاً بعداً دوباره تلاش کنید."
        )

        return

    configs = get_vless_configs(sub_link)

    region = "🌐"

    if configs and "#" in configs[0]:
        region = configs[0].split("#")[-1].strip()

    set_last_subscription(user.id, sub_link)

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
🌍 ریجن: <b>{region}</b>

🔗 لینک ساب:
<code>{sub_link}</code>

📄 کانفیگ‌ها:
<b>برای مشاهده و کپی کانفیگ‌ها، روی دکمه «📄 مشاهده کانفیگ‌ها» بزنید.</b>

━━━━━━━━━━━━━━
<i>🤖 By: @{(await context.bot.get_me()).username}</i>

<b>در صورت بروز هرگونه مشکل، از طریق دکمه «💬 پشتیبانی» با ما در ارتباط باشید.</b>
"""

    context.user_data["subscription_text"] = subscription_text
    context.user_data["sub_link"] = sub_link
    context.user_data["subscription_name"] = service_name

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📄 مشاهده کانفیگ‌ها",
                    callback_data="show_configs",
                ),
                InlineKeyboardButton(
                    "🔗 باز کردن لینک ساب",
                    url=sub_link,
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔄 تمدید اشتراک",
                    callback_data="extend_test_subscription",
                ),
                InlineKeyboardButton(
                    "✏️ تغییر نام سرویس",
                    callback_data="rename_service",
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

    except Exception as e:

        print(e)

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
🌐 ریجن: آمریکا 🇺🇸

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

    except Exception as e:

        print(e)

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

    await message.reply_text(
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
        "🌍📰\n\n"
        "لطفاً کمی صبر کنید...\n\n"
        "🤖 در حال دریافت و آماده‌سازی اخبار هستیم. ✨"
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

        join_text = iran_time.strftime("%Y/%m/%d - %H:%M")

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

    if isinstance(services, list):

        for service in services:

            service_name = service.get("name", "")

            if service_name.startswith(f"TG-{update.effective_user.id}-"):

                buttons.append(
                    [
                        InlineKeyboardButton(
                            service_name,
                            callback_data=f"subscription_{service.get('id')}",
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
    test_api_root()
    test_patch_user(service_id)

    if not service:
        await query.edit_message_text("❌ سرویس پیدا نشد.")
        return

    # اطلاعات سرویس
    name = service.get("name", "-")
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

    days_left = (expiry_dt - datetime.now()).days

    if days_left < 0:
        days_left = 0

    # اتصال همزمان
    conn = service.get("connLimit")

    if conn in (None, 0):
        conn_text = "نامحدود"
    else:
        conn_text = str(conn)

    # لینک ساب و ریجن
    sub_link = "-"
    region = "🌐"

    try:
        sub_link = get_last_subscription(query.from_user.id)

        if sub_link:

            configs = get_vless_configs(sub_link)

            if configs and "#" in configs[0]:
                region = configs[0].split("#")[-1]

    except Exception:
        pass

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
🌍 ریجن: <b>{region}</b>

🔗 لینک ساب:
<code>{sub_link}</code>

📄 کانفیگ‌ها:
<b>برای مشاهده و کپی کانفیگ‌ها، روی دکمه «📄 مشاهده کانفیگ‌ها» بزنید.</b>

━━━━━━━━━━━━━━
<i>🤖 By: @{(await context.bot.get_me()).username}</i>

<b>در صورت بروز هرگونه مشکل، از طریق دکمه «💬 ارتباط با پشتیبانی» با ما در ارتباط باشید.</b>
"""

    # ذخیره اطلاعات برای برگشت و عملیات بعدی
    context.user_data["subscription_text"] = text
    context.user_data["subscription_service_id"] = service_id
    context.user_data["subscription_sub_link"] = sub_link
    context.user_data["subscription_name"] = name

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
                    url=sub_link,
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔄 تمدید اشتراک",
                    callback_data=f"renew_{service_id}",
                ),
                InlineKeyboardButton(
                    "✏️ تغییر نام سرویس",
                    callback_data=f"rename_{service_id}",
                ),
            ],
        ]
    )

    await query.edit_message_text(
        text,
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

💳 مبلغ ۱۰٬۰۰۰ تومان به اعتبار حساب شما اضافه شد.
""",
                )
            except Exception:
                pass

        # -----------------------------------------------

        await query.message.delete()

        await context.bot.send_message(
            chat_id=user_id,
            text="""✅ عضویت شما تایید شد.

🎉 به ربات خوش اومدید

🔮 برای ادامه، از دکمه‌های زیر استفاده کنید:""",
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


# ------------------ rename service ------------------


@membership_required
async def rename_service_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer(
        "🚧 این قابلیت در حال حاضر غیرفعال است و به‌زودی فعال خواهد شد.",
        show_alert=True,
    )


# ------------------- HANDLERS ------------------


def get_handlers():

    return [
        CommandHandler("test", test_command),
        CommandHandler("admin", admin_panel),
        CommandHandler("stats", stats),
        CommandHandler("start", start),
        MessageHandler(filters.Regex("^👨‍💻 سازنده ربات$"), about_me),
        MessageHandler(filters.Regex("^🛠 خدمات$"), services),
        MessageHandler(filters.Regex("^🔙 بازگشت$"), back_to_main),
        MessageHandler(filters.Regex("^🔐 کانفیگ VPN$"), vpn_menu),
        MessageHandler(filters.Regex("^🎁 اشتراک تست$"), vpn_test),
        MessageHandler(filters.Regex("^💎 خرید اشتراک$"), buy_vpn),
        MessageHandler(
            filters.Regex("^👥 زیرمجموعه گیری$"),
            referral_menu,
        ),
        MessageHandler(
            filters.Regex("^📚 آموزش اتصال$"),
            vpn_guide_callback,
        ),
        MessageHandler(filters.Regex("^👤 پروفایل$"), profile),
        MessageHandler(filters.Regex("^🌍 اخبار روز$"), crypto_news),
        MessageHandler(filters.Regex("^📦 اشتراک‌های من$"), my_subscriptions),
        MessageHandler(filters.Regex("^💬 ارتباط با پشتیبانی$"), contact_me),
        CallbackQueryHandler(check_join_callback, pattern="^check_join$"),
        CallbackQueryHandler(next_news, pattern="next_news"),
        CallbackQueryHandler(vpn_test_request, pattern="^vpn_test_request$"),
        CallbackQueryHandler(
            show_configs,
            pattern=r"^show_configs",
        ),
        CallbackQueryHandler(buy_subscription_callback, pattern="^buy_subscription$"),
        CallbackQueryHandler(
            extend_test_subscription, pattern="^extend_test_subscription$"
        ),
        CallbackQueryHandler(
            back_to_subscription,
            pattern="^back_to_subscription$",
        ),
        CallbackQueryHandler(
            subscription_details,
            pattern="^subscription_",
        ),
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
        CallbackQueryHandler(referral_menu, pattern="^referral_menu$"),
        CallbackQueryHandler(
            rename_service_callback,
            pattern=r"^rename",
        ),
        CallbackQueryHandler(
            extend_test_subscription,
            pattern="^renew_",
        ),
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
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            receive_new_service_name,
        ),
    ]
