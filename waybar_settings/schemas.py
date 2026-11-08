"""Load the module schemas in waybar_settings/schemas/."""

from functools import cache
from pathlib import Path
import json

SCHEMA_DIR = Path(__file__).parent / "schemas"

# Modules that need a user-chosen name: "custom/<name>", "group/<name>".
NAMED_MODULES = {"custom", "group"}

# Prefixes shown next to the title in the module picker, so that the
# many "Workspaces" / "Window" modules can be told apart.
COMPOSITORS = {
    "hyprland": "Hyprland",
    "sway": "Sway",
    "niri": "Niri",
    "river": "River",
    "dwl": "dwl",
    "mango": "Mango",
    "umbriel": "Umbriel",
    "wayfire": "Wayfire",
    "ext": "Any compositor",
    "wlr": "wlroots",
}


def base_name(module):
    """'battery#bat2' -> 'battery', 'custom/menu' -> 'custom'."""
    name = module.split("#", 1)[0]
    prefix = name.split("/", 1)[0]
    if prefix in NAMED_MODULES:
        return prefix
    return name


@cache
def _load(file_name):
    path = SCHEMA_DIR / file_name
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as file:
        return json.load(file)


def load_schema(module):
    """Return the schema of a module, or None if there is none."""
    return _load(base_name(module).replace("/", "_") + ".json")


def bar_schema():
    return _load("bar.json")


@cache
def available_modules():
    """All modules that can be added to the bar, sorted by title."""
    modules = []
    for path in SCHEMA_DIR.glob("*.json"):
        schema = _load(path.name)
        if schema["module"] != "bar":
            modules.append(schema)
    return sorted(modules, key=lambda s: picker_title(s["module"]).lower())


def picker_title(module):
    """Title shown in the module picker: 'Workspaces (Hyprland)'."""
    schema = load_schema(module)
    title = schema["title"] if schema else module
    prefix = module.split("/", 1)[0] if "/" in module else None
    if prefix in COMPOSITORS:
        title += f" ({COMPOSITORS[prefix]})"
    return title


def display_title(module):
    """Title shown in the sidebar and in the layout:
    'custom/menu' -> 'Custom: menu', 'battery#bat2' -> 'Battery (bat2)'."""
    schema = load_schema(module)
    name, _, instance = module.partition("#")
    prefix = name.split("/", 1)[0]

    if prefix in NAMED_MODULES and "/" in name:
        title = f"{prefix.capitalize()}: {name.split('/', 1)[1]}"
    elif schema:
        title = schema["title"]
    else:
        title = name

    if instance:
        title += f" ({instance})"
    return title
