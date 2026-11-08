from pathlib import Path
import json
import shutil

import json5

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

def save_config(config):
    DIR_PATH.mkdir(parents=True, exist_ok=True)

    if USER_CONFIG_PATH.exists() and not BACKUP_PATH.exists():
        shutil.copy2(USER_CONFIG_PATH, BACKUP_PATH)
    
    with open(USER_CONFIG_PATH, "w", encoding="utf-8") as file:
        json.dump(config, file, indent=4, ensure_ascii=False)