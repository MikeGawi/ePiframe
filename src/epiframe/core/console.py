"""Helpers of the interactive console tools (setup, tests)."""

import getpass
import sys
from collections.abc import Callable

Ask = Callable[[str], str]
Say = Callable[[str], None]


def ask_yes(ask: Ask, question: str, default: bool) -> bool:
    """Ask a yes/no ``question`` until the answer is one; Enter gives ``default``."""
    choices = "[Y/n]" if default else "[y/N]"
    while True:
        answer = ask(f"{question} {choices} ").strip().lower()
        if not answer:
            return default
        if answer in ("y", "yes", "n", "no"):
            return answer.startswith("y")


def read_secret(prompt: str) -> str:
    """Hidden input on a terminal (passwords, tokens); ``input`` when piped.

    ``getpass`` reads ``/dev/tty`` even when stdin is a pipe (installer, tests),
    so a piped run would wait for the keyboard.
    """
    return getpass.getpass(prompt) if sys.stdin.isatty() else input(prompt)
