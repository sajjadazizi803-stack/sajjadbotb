from telegram.ext import Application, TypeHandler
from telegram import Update

from config import TOKEN
from handlers import get_handlers, global_membership_check, set_bot_commands
from database import init_db


def main():

    # ساخت دیتابیس
    init_db()

    app = Application.builder().token(TOKEN).post_init(set_bot_commands).build()

    # چک عضویت سراسری
    app.add_handler(
        TypeHandler(Update, global_membership_check),
        group=-1,
    )

    for handler in get_handlers():
        app.add_handler(handler)

    print("✅ Bot Started")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
