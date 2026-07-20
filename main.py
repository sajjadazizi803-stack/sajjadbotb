from telegram.ext import Application, TypeHandler
from telegram import Update
from config import TOKEN
from handlers import get_handlers
from database import init_db
from handlers import global_membership_check


def main():

    # ساخت دیتابیس و جدول‌ها
    init_db()

    app = Application.builder().token(TOKEN).build()

    # چک عضویت سراسری قبل از اجرای هر هندلر دیگر
    app.add_handler(TypeHandler(Update, global_membership_check), group=-1)

    for handler in get_handlers():
        app.add_handler(handler)

    print("✅ Bot Started")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
