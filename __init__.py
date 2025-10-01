"""Crawler package exposing scraping CLI."""

from importlib import import_module
from typing import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    entry = import_module("crawler.main")
    return entry.main(argv)


__all__ = ["main"]
