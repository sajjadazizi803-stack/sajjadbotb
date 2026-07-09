from telegram.ext import Application

from config import TOKEN
from handlers import get_handlers


def main():

    app = Application.builder().token(TOKEN).build()

    for handler in get_handlers():
        app.add_handler(handler)

    print("✅ Bot Started")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()