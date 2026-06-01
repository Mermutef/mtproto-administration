"""Utility functions used across the project."""

import html


def escape_html(text: str) -> str:
    """Escape HTML special characters in a string.

    Args:
        text: The input string.

    Returns:
        The HTML-escaped version of the input.
    """
    return html.escape(str(text))
