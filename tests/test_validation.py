#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for src/Validation.py.

These checks guard the arguments that the pkexec helper scripts accept as
root. They use synthetic values only and need neither root nor apt.

Run from the project root:
    python3 -B -m unittest discover -s tests -v
"""

import json
import os
import sys
import unittest

# The application ships its modules as plain scripts in src/, not as a
# package, so the tests import them the same way the helpers do.
PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(PROJECT_DIR, "src"))

from Validation import is_safe_sources, parse_packages, validate_timestamp  # noqa: E402


class IsSafeSourcesTest(unittest.TestCase):
    """Behaviour of is_safe_sources for accepted and rejected sources."""

    def test_accepts_official_lines(self):
        """Plain deb/deb-src lines, comments and blank lines are accepted."""
        text = ("# Pardus\n"
                "deb http://depo.pardus.org.tr/pardus yirmibes main contrib non-free non-free-firmware\n"
                "\n"
                "deb-src http://depo.pardus.org.tr/pardus yirmibes main\n")

        self.assertTrue(is_safe_sources(text))

    def test_accepts_shipped_default_sources(self):
        """Every default in data/sources.json passes, so fixsources keeps working."""
        with open(os.path.join(PROJECT_DIR, "data", "sources.json"), encoding="utf-8") as f:
            static_sources = json.load(f)

        for distro_name, releases in static_sources.items():
            for release in releases:
                with self.subTest(distro=distro_name, release=release["name"]):
                    self.assertTrue(is_safe_sources(release["sources"]))

    def test_rejects_empty_input(self):
        """Empty, blank and None input never counts as a valid sources list."""
        for value in (None, "", "   ", "\n\n"):
            with self.subTest(value=value):
                self.assertFalse(is_safe_sources(value))

    def test_rejects_non_deb_lines(self):
        """Anything that is not a deb/deb-src line is rejected."""
        for line in ("rm -rf /", "debx http://example.org x main", "Types: deb"):
            with self.subTest(line=line):
                self.assertFalse(is_safe_sources(line))

    def test_rejects_blacklisted_options(self):
        """Options that disable signature checks or use local media fail."""
        lines = (
            "deb [trusted=yes] http://example.org/debian stable main",
            "deb [ trusted = true ] http://example.org/debian stable main",
            "deb [allow-insecure=yes] http://example.org/debian stable main",
            "deb [signed-by=/tmp/key.gpg] http://example.org/debian stable main",
            "deb file:///tmp/repo ./",
            "deb copy:///tmp/repo ./",
            "deb cdrom://disk/ stable main",
        )

        for line in lines:
            with self.subTest(line=line):
                self.assertFalse(is_safe_sources(line))

    def test_one_bad_line_rejects_whole_text(self):
        """A single bad line invalidates an otherwise valid text."""
        text = ("deb http://depo.pardus.org.tr/pardus yirmibes main\n"
                "deb [trusted=yes] http://example.org/debian stable main\n")

        self.assertFalse(is_safe_sources(text))

    def test_accepts_allowed_options_and_transports(self):
        """Options that only select content and remote transports pass."""
        lines = (
            "deb [arch=amd64] http://depo.pardus.org.tr/pardus yirmibes main",
            "deb [ arch=amd64,i386 lang=tr ] https://example.org/debian stable main",
            "deb [arch+=arm64 target=Contents-deb] https://example.org/debian stable main",
            "deb\thttps://example.org/debian\tstable\tmain",
            "deb tor+https://example.onion/debian stable main",
            "deb mirror+http://example.org/mirrors.txt stable main",
            "deb https://example.org/repo ./",
            "deb http://depo.pardus.org.tr/pardus yirmibes main # comment",
        )

        for line in lines:
            with self.subTest(line=line):
                self.assertTrue(is_safe_sources(line))

    def test_rejects_options_outside_allow_list(self):
        """Every option that weakens verification is rejected (S2 bypasses)."""
        options = (
            "trusted=on", "trusted=1", "trusted=with", "trusted=enable",
            "allow-downgrade-to-insecure=yes", "allow-weak=yes",
            "check-valid-until=no", "check-date=no", "date-max-future=99999",
            "signed-by=/home/user/key.gpg", "inrelease-path=x",
            "arch=amd64;trusted=yes", "arch = amd64",
        )

        for option in options:
            line = "deb [{}] http://example.org/debian stable main".format(option)
            with self.subTest(line=line):
                self.assertFalse(is_safe_sources(line))

    def test_rejects_unsupported_transports_and_malformed_lines(self):
        """Local or unknown transports and incomplete lines are rejected."""
        lines = (
            "deb file:/tmp/repo ./",
            "deb ssh://host/repo stable main",
            "deb ftp://example.org/debian stable main",
            "deb http://example.org/debian",
            "deb [arch=amd64 http://example.org/debian stable main",
            "deb[trusted=yes] http://example.org/debian stable main",
            "deb http://example.org/debian stable main$(id)",
            "deb",
        )

        for line in lines:
            with self.subTest(line=line):
                self.assertFalse(is_safe_sources(line))

    def test_rejects_quoted_option_values(self):
        """Quoted values are honoured by apt, so they must not pass.

        Regression for https://github.com/pardus/pardus-update/issues/25:
        [trusted="yes"] slipped past the old substring blacklist.
        """
        lines = (
            'deb [trusted="yes"] http://127.0.0.1:18081/ ./',
            "deb [trusted='yes'] http://127.0.0.1:18081/ ./",
            'deb [arch="amd64"] http://example.org/debian stable main',
            "deb [trusted\t=\tyes] http://example.org/debian stable main",
            "deb [trusted =yes] http://example.org/debian stable main",
            "deb [TRUSTED=YES] http://example.org/debian stable main",
        )

        for line in lines:
            with self.subTest(line=line):
                self.assertFalse(is_safe_sources(line))

    def test_rejects_quoting_characters_in_uri(self):
        """Quotes, brackets, control and non-ASCII characters in the URI fail."""
        for uri in ('http://a"/', "http://a/[trusted=yes]", "http://a/]",
                    "http://a/\x00", "http://dep\u00f6.org/"):
            line = "deb {} stable main".format(uri)
            with self.subTest(line=line):
                self.assertFalse(is_safe_sources(line))

    def test_comment_or_line_break_cannot_split_option_block(self):
        """A "#" or any line separator inside [...] leaves it unclosed."""
        for sep in ("#", "\r", "\n", "\x0b", "\x0c", "\x85", "\u2028"):
            text = "deb [arch=amd64{}trusted=yes] http://example.org/debian stable main".format(sep)
            with self.subTest(separator=repr(sep)):
                self.assertFalse(is_safe_sources(text))

    def test_rejects_second_option_block_and_deb822(self):
        """Only one leading option block exists; deb822 stanzas are rejected."""
        texts = (
            "deb [arch=amd64] [trusted=yes] http://example.org/debian stable main",
            "Types: deb\nURIs: http://example.org/debian\nSuites: stable\nTrusted: yes",
        )

        for text in texts:
            with self.subTest(text=text):
                self.assertFalse(is_safe_sources(text))


class ParsePackagesTest(unittest.TestCase):
    """Behaviour of parse_packages for keep/residual package lists."""

    def test_empty_input_returns_empty_list(self):
        """No packages means an empty list, not an error."""
        for value in (None, "", "   "):
            with self.subTest(value=value):
                self.assertEqual(parse_packages(value), [])

    def test_valid_names_keep_order(self):
        """Valid names, including arch qualifiers, are returned in order."""
        self.assertEqual(
            parse_packages("firmware-b43-installer  libc6:amd64\tg++ python3.13"),
            ["firmware-b43-installer", "libc6:amd64", "g++", "python3.13"])

    def test_rejects_option_like_and_invalid_names(self):
        """Values that apt could read as options or shell syntax are rejected."""
        for value in ("-oAPT::Update::Pre-Invoke=id", "--purge", "Bad", "a",
                      "pkg;id", "pkg$(id)", "../pkg", "pkg:"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_packages("vim " + value)


class ValidateTimestampTest(unittest.TestCase):
    """Behaviour of validate_timestamp for the lastupdate setting."""

    def test_normalizes_valid_values(self):
        """Non-negative integers are returned as decimal text."""
        self.assertEqual(validate_timestamp("0"), "0")
        self.assertEqual(validate_timestamp(" 1760900000 "), "1760900000")
        self.assertEqual(validate_timestamp("0042"), "42")

    def test_rejects_invalid_values(self):
        """Negative, fractional and non-numeric values raise ValueError."""
        for value in ("-1", "1.5", "abc", "", "1e9", "0x10"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_timestamp(value)


if __name__ == "__main__":
    unittest.main()
