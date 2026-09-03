"""Blueprint containing the unchanged legacy HTTP surface.

Handlers remain implemented in ``web_app.py`` during this incremental step so
their existing dependencies and response bodies stay untouched. The
blueprint is the explicit registration boundary; a later API phase can add
versioned handlers without changing these routes.
"""

from flask import Blueprint


def create_legacy_blueprint() -> Blueprint:
    """Create a fresh blueprint for one Flask application instance."""
    return Blueprint("legacy", __name__)


__all__ = ["create_legacy_blueprint"]
