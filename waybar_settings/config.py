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

def used_modules(config):
    all_modules = config.get("modules-left", []) + config.get("modules-center", []) + config.get("modules-right", [])
    unique_modules = []
    for module in all_modules:
        if module not in unique_modules:
            unique_modules.append(module)
    return unique_modules

def save_config(config):
    DIR_PATH.mkdir(parents=True, exist_ok=True)

    if USER_CONFIG_PATH.exists() and not BACKUP_PATH.exists():
        shutil.copy2(USER_CONFIG_PATH, BACKUP_PATH)
    
    with open(USER_CONFIG_PATH, "w", encoding="utf-8") as file:
        json.dump(config, file, indent=4, ensure_ascii=False)