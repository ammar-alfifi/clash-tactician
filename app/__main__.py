"""Allow ``python -m app`` (used by the Docker image)."""

from app.bot.app import main

if __name__ == "__main__":
    main()
