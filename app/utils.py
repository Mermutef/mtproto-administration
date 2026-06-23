"""Utility functions used across the project."""
import html
import re

from anyascii import anyascii


def sanitize_username(username: str) -> str:
    """Clean up a username: transliterate any script, keep safe chars.

    Uses the ``anyascii`` library (transliterates Russian, Chinese,
    Arabic, French, etc. to ASCII).

    Args:
        username: Raw input (any script, spaces, etc.).

    Returns:
        A sanitised ASCII-only string safe for use as a 3x-ui email.
    """
    s = anyascii(username)
    s = s.strip().replace(' ', '_').replace('-', '_')
    s = re.sub(r'[^a-zA-Z0-9_]', '_', s)
    s = re.sub(r'_+', '_', s)
    # If the result is already pure ASCII and doesn't contain
    # characters that `anyascii` would change, it's already clean.
    # Don't strip leading underscores — they are meaningful for
    # names like ``_______someuser``.
    return s if s else "user"


def escape_html(text: str) -> str:
    """Escape HTML special characters in a string."""
    return html.escape(str(text))
