"""@mention parsing utility.

Extracts ``@username`` references from text content and returns
the set of unique usernames found.  Used by the thread and comment
services to build ``MENTIONED`` notification events.

The regex intentionally mirrors the ``USERNAME_PATTERN`` accepted
by the user service registration endpoint.
"""

import re

# Matches @username where username is 3-50 alphanumeric + underscore chars.
# Negative lookbehind ensures we don't match email prefixes (e.g. user@domain).
_MENTION_RE = re.compile(r"(?<!\S)@([A-Za-z0-9_]{3,50})\b")


def extract_mentions(text: str) -> set[str]:
    """Return the set of unique usernames mentioned in *text*.

    Examples
    --------
    >>> extract_mentions("Hey @john_doe check this out @jane!")
    {'john_doe'}
    >>> extract_mentions("No mentions here")
    set()
    """
    return set(_MENTION_RE.findall(text))
