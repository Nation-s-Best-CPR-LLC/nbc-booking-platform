"""Entry point.

Production (Replit Reserved VM):  gunicorn --bind 0.0.0.0:5000 --workers 2 wsgi:app
Local development:                flask --app wsgi run --debug
"""

from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402  (load .env before settings are read)

app = create_app()
