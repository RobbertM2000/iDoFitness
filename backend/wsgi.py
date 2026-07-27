"""Gunicorn entrypoint.

Gunicorn wants a plain WSGI callable (`module:app`), not the app-factory
function itself, so this module just calls the factory once at import time.

Run in prod with:
    gunicorn --bind 0.0.0.0:5000 wsgi:app
"""
from app import create_app

app = create_app()
