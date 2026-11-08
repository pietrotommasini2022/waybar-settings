from pathlib import Path
import json
import shutil

import json5

from . import jsonc

USER_CONFIG_PATH = Path.home() / ".config" / "waybar" / "config.jsonc"
DEFAULT_PATH = Path("/etc/xdg/waybar/config.jsonc")
BACKUP_PATH = Path.home() / ".config" / "waybar" / "config.jsonc.bak"
DIR_PATH = Path.home() / ".config" / "waybar"

def find_config_path():
    config_path = USER_CONFIG_PATH
    if config_path.exists():
        path = config_path
    else:
        path = DEFAULT_PATH
    return path 



def load_config():
    config_path = find_config_path()
    with open(config_path) as file:
        config = json5.load(file)
    return config

COLUMNS = ("modules-left", "modules-center", "modules-right")


def first_bar(config):
    """Waybar accepts a list of bars: for now we edit the first one."""
    if isinstance(config, list):
        return config[0] if config else {}
    return config


def used_modules(config):
    """Modules in the three columns, plus the modules inside groups."""
    unique_modules = []

    def add(modules):
        for module in modules:
            if module in unique_modules:
                continue
            unique_modules.append(module)
            if module.startswith("group/"):
                add(config.get(module, {}).get("modules", []))

    for column in COLUMNS:
        add(config.get(column, []))
    return unique_modules

USER_STYLE_PATH = DIR_PATH / "style.css"
DEFAULT_STYLE_PATH = Path("/etc/xdg/waybar/style.css")


def ensure_user_file(user_path, default_path):
    """Make sure the user has their own copy of a file to edit by hand:
    copy Waybar's default if there is none. Returns the user path."""
    if not user_path.exists():
        DIR_PATH.mkdir(parents=True, exist_ok=True)
        if default_path.exists():
            shutil.copy2(default_path, user_path)
        else:
            user_path.touch()
    return user_path


def user_config_file():
    return ensure_user_file(USER_CONFIG_PATH, DEFAULT_PATH)


def user_style_file():
    return ensure_user_file(USER_STYLE_PATH, DEFAULT_STYLE_PATH)


def save_config(config):
    DIR_PATH.mkdir(parents=True, exist_ok=True)

    if USER_CONFIG_PATH.exists() and not BACKUP_PATH.exists():
        shutil.copy2(USER_CONFIG_PATH, BACKUP_PATH)
    
    text = config_text(config)  # before writing: it reads the current file
    temporary = USER_CONFIG_PATH.with_name(USER_CONFIG_PATH.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(USER_CONFIG_PATH)  # atomic: never a half-written file


def config_text(config):
    """The new text of the config file. Only the parts that changed are
    rewritten, so the user's comments and formatting are kept.
    Starts from Waybar's default file when the user has none yet."""
    try:
        text = find_config_path().read_text(encoding="utf-8")
    except OSError:
        text = ""
    try:
        new_text = jsonc.update(text, config)
        if json5.loads(new_text) == config:
            return new_text
    except (ValueError, KeyError, IndexError, AttributeError, TypeError):
        pass
    # Safety net: a file we could not edit in place is rewritten from
    # scratch (the first version of the file is in config.jsonc.bak).
    return json.dumps(config, indent=4, ensure_ascii=False) + "\n"