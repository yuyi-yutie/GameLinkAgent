"""Local web UI: an HTTP + SSE surface in front of the shared pipeline layer.

Importing this package requires the optional ``web`` extra
(``pip install -e ".[web]"``); the CLI imports it lazily for that reason.
"""

from gamelink.web.app import BUILD_HINT, create_app, serve

__all__ = ["BUILD_HINT", "create_app", "serve"]
