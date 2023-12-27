"""Utility functions."""
import re


def slugify(name: str) -> str:
    """Turn the name into a valid slug"""
    return re.sub("[^a-z0-9]", "-", name.lower())
