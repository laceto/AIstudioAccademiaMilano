import logging
import os

from dotenv import load_dotenv

load_dotenv()

from src.bot import build_application  # noqa: E402

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


def main() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = build_application(token)
    print("Mindful Pause Bot is running. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
