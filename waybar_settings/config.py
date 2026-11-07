import json5
from pathlib import Path

def find_config_path():
    config_path = Path.home() / ".config" / "waybar" / "config.jsonc"
    if config_path.exists():
      path = config_path
    else:
        path = Path("/etc/xdg/waybar/config.jsonc")
    return path 



def load_config():
    config_path = find_config_path()
    with open(config_path) as file:
        config = json5.load(file)
    return config