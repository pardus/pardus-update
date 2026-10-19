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

SOURCES_BLACKLISTED_TERMS = [
    "trusted=yes", "trusted=true",
    "allow-insecure",
    "signed-by=",
    "file://", "copy://", "cdrom://"
]


def is_safe_sources(sources_text):
    """Check that a sources.list text contains only acceptable deb lines.

    Comment and empty lines are skipped. Every other line must start with
    "deb" or "deb-src" and must not contain a blacklisted option or scheme.

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

        if not re.match(r"^deb(-src)?\s+", line):
            return False

        # Spaces are removed so "trusted = yes" style spellings still match.
        compact_line = line.lower().replace(" ", "")
        for term in SOURCES_BLACKLISTED_TERMS:
            if term.replace(" ", "") in compact_line:
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
