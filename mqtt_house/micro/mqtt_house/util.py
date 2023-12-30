import re


def slugify(name):
    """Slugify a name."""
    name = name.lower()
    return re.sub("[^a-z0-9]", "-", name)
