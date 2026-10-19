#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Input validation shared by the pkexec helper scripts.

The helpers (SysActions.py, AptSourceActions.py, SystemSettingsWrite.py)
run as root and can be started by any process in the user session with
arbitrary arguments, so every argument is untrusted. Keeping the checks in
one module avoids divergent copies and lets them be unit tested without
root or apt side effects.
"""

import re

# Debian package name, optionally with an architecture qualifier. The first
# character cannot be "-", so a value can never be read as an apt option.
PACKAGE_NAME_RE = re.compile(r'^[a-z0-9][a-z0-9+.-]+(?::[a-z0-9]+)?$')

# Transports accepted in a deb line. Local transports (file:, copy:, cdrom:)
# are left out because they let the caller point apt at a directory it
# controls; remote shell transports (ssh:, rsh:) are not used for Pardus.
SOURCES_ALLOWED_SCHEMES = (
    "http", "https",
    "tor+http", "tor+https",
    "mirror+http", "mirror+https",
)

# Options that only select what is downloaded. Everything else in [...]
# (trusted, signed-by, allow-insecure, allow-weak, check-valid-until, ...)
# changes how apt verifies a repository and is rejected. The optional "+"
# or "-" allows the arch+=/arch-= forms.
SOURCES_OPTION_RE = re.compile(r'^(arch|lang|target)(\+|-)?=[A-Za-z0-9_.,-]+$')

SOURCES_URI_RE = re.compile(r'^([a-z+]+)://\S+$')

# Suite and component names, e.g. "yirmibes", "yirmibes-security",
# "stable/updates", "./", "main", "non-free-firmware".
SOURCES_WORD_RE = re.compile(r'^[A-Za-z0-9_.~/+-]+$')


def _split_sources_options(rest):
    """Split the optional "[ ... ]" block from the rest of a deb line.

    Args:
        rest: The deb line without its leading "deb"/"deb-src" token.

    Returns:
        tuple[list[str], str] | None: Option tokens and the remaining text,
        or None if a "[" is opened but never closed.
    """
    rest = rest.strip()
    if not rest.startswith("["):
        return [], rest

    closing = rest.find("]")
    if closing < 0:
        return None

    return rest[1:closing].split(), rest[closing + 1:]


def _is_safe_sources_line(line):
    """Check one non-comment one-line-style sources.list entry.

    Args:
        line: A stripped line that is not empty and not a comment.

    Returns:
        bool: True if the line is a deb/deb-src entry with only allowed
        options, an allowed transport, a suite and valid component names.
    """
    # apt treats "#" as the start of a comment anywhere on the line.
    line = line.split("#", 1)[0].strip()
    if not line:
        return True

    parts = line.split(None, 1)
    if parts[0] not in ("deb", "deb-src"):
        return False

    split = _split_sources_options(parts[1] if len(parts) > 1 else "")
    if split is None:
        return False

    options, rest = split
    for option in options:
        if not SOURCES_OPTION_RE.fullmatch(option):
            return False

    words = rest.split()
    # At least a URI and a suite are required.
    if len(words) < 2:
        return False

    uri_match = SOURCES_URI_RE.fullmatch(words[0])
    if not uri_match or uri_match.group(1) not in SOURCES_ALLOWED_SCHEMES:
        return False

    return all(SOURCES_WORD_RE.fullmatch(word) for word in words[1:])


def is_safe_sources(sources_text):
    """Check that a sources.list text contains only acceptable deb lines.

    The check is an allow-list: comment and empty lines are skipped, every
    other line must be a one-line-style deb/deb-src entry whose "[...]"
    options only select architectures, languages or targets and whose URI
    uses a remote transport. Any option that weakens signature checks is
    rejected, because the text comes from an unprivileged caller and is
    written to /etc/apt as root.

    Args:
        sources_text: sources.list content passed by the caller.

    Returns:
        bool: True if the text is non-empty and every line is acceptable.
    """
    if not sources_text or not str(sources_text).strip():
        return False

    for line in str(sources_text).splitlines():

        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if not _is_safe_sources_line(line):
            return False

    return True


def parse_packages(packages):
    """Split a space separated package list and validate every name.

    Args:
        packages: Package names separated by whitespace; may be empty or None.

    Returns:
        list[str]: Valid package names in input order; empty for no input.

    Raises:
        ValueError: If any item is not a valid Debian package name.
    """
    if not packages or not packages.strip():
        return []

    valid_packages = []

    for item in packages.split():
        item = item.strip()
        if not item:
            continue

        if PACKAGE_NAME_RE.fullmatch(item):
            valid_packages.append(item)
        else:
            raise ValueError(f"Invalid package name detected: '{item}'")

    return valid_packages


def validate_timestamp(value):
    """Validate a Unix timestamp given as text.

    Args:
        value: Timestamp text from the command line.

    Returns:
        str: The normalized decimal timestamp.

    Raises:
        ValueError: If the value is not a non-negative integer.
    """
    try:
        ts = int(value)
        if ts < 0:
            raise ValueError
        return str(ts)
    except ValueError:
        raise ValueError("Invalid timestamp")
