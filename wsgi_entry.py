"""WSGI import target; Gunicorn owns the process lifecycle."""

from web_app import app


__all__ = ["app"]
