"""Values to propose in the drop-down menu of text options.

Most text options are free (a format, a command…), so the menu does not limit
what can be written: it offers ready-made values that fit the option.

    kind(key)               -> what kind of option this is (cheap)
    suggestions(kind, ...)  -> [Section], computed when the menu opens
"""

from dataclasses import dataclass, field
from pathlib import Path
import os
import shlex
import shutil
import subprocess


@dataclass
class Suggestion:
    value: str
    label: str = ""
    description: str = ""
    insert: bool = False  # True: insert at the cursor instead of replacing


@dataclass
class Section:
    title: str
    items: list = field(default_factory=list)


# ---------------------------------------------------------------- kinds

COMMAND_KEYS = ("on-click", "on-scroll", "on-update", "exec")
PATH_KEYS = {
    "menu-file", "path", "image-path", "cava_config", "avatar", "include",
    "module_path", "hwmon-path", "hwmon-path-abs", "input-filename", "open-path",
}
SYSTEM_KEYS = {
    "timezone", "locale", "output", "interface", "device", "bat", "adapter",
    "hwmon-path", "icon-theme", "player", "native-path",
}


def kind(key):
    if key in SYSTEM_KEYS:
        return key
    if key.startswith(COMMAND_KEYS):
        return "command"
    if "format" in key:
        return "format"
    if key == "ellipsis":
        return "ellipsis"
    if key == "return-type":
        return "return-type"
    return None


def is_path(key):
    return key in PATH_KEYS


# ---------------------------------------------------------------- commands

def terminal():
    """The terminal emulator used to run text programs (btop, nmtui…)."""
    from .editor import find_terminal
    found = find_terminal()
    return found[0] if found else None


# Commands per module; "{term}" is replaced by the terminal command.
COMMANDS = {
    "audio": [
        ("pavucontrol", "Volume control"),
        ("wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle", "Mute / unmute"),
        ("wpctl set-volume -l 1.0 @DEFAULT_AUDIO_SINK@ 5%+", "Volume up"),
        ("wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-", "Volume down"),
        ("pamixer -t", "Mute / unmute"),
        ("pamixer -i 5", "Volume up"),
        ("pamixer -d 5", "Volume down"),
        ("pactl set-sink-mute @DEFAULT_SINK@ toggle", "Mute / unmute"),
        ("helvum", "Audio routing"),
    ],
    "backlight": [
        ("brightnessctl set +5%", "Brighter"),
        ("brightnessctl set 5%-", "Darker"),
        ("light -A 5", "Brighter"),
        ("light -U 5", "Darker"),
    ],
    "media": [
        ("playerctl play-pause", "Play / pause"),
        ("playerctl next", "Next track"),
        ("playerctl previous", "Previous track"),
        ("mpc toggle", "Play / pause (MPD)"),
        ("mpc next", "Next track (MPD)"),
        ("mpc prev", "Previous track (MPD)"),
    ],
    "network": [
        ("nm-connection-editor", "Network connections"),
        ("{term} nmtui", "Network manager in the terminal"),
        ("iwgtk", "Wi-Fi settings"),
        ("{term} impala", "Wi-Fi settings in the terminal"),
    ],
    "bluetooth": [
        ("blueman-manager", "Bluetooth devices"),
        ("blueberry", "Bluetooth devices"),
        ("overskride", "Bluetooth devices"),
        ("{term} bluetui", "Bluetooth in the terminal"),
        ("bluetoothctl power on", "Turn Bluetooth on"),
        ("bluetoothctl power off", "Turn Bluetooth off"),
    ],
    "system": [
        ("{term} btop", "System monitor"),
        ("{term} htop", "System monitor"),
        ("{term} top", "System monitor"),
        ("gnome-system-monitor", "System monitor"),
        ("missioncenter", "System monitor"),
    ],
    "clock": [
        ("gnome-calendar", "Calendar"),
        ("{term} calcurse", "Calendar in the terminal"),
    ],
    "power": [
        ("powerprofilesctl set performance", "Performance mode"),
        ("powerprofilesctl set balanced", "Balanced mode"),
        ("powerprofilesctl set power-saver", "Power saver mode"),
        ("wlogout", "Power menu"),
        ("systemctl suspend", "Suspend"),
    ],
    "launcher": [
        ("rofi -show drun", "App launcher (rofi)"),
        ("wofi --show drun", "App launcher (wofi)"),
        ("fuzzel", "App launcher (fuzzel)"),
        ("walker", "App launcher (walker)"),
        ("swaync-client -t -sw", "Notification center"),
        ("wlogout", "Power menu"),
        ("hyprlock", "Lock the screen"),
        ("swaylock", "Lock the screen"),
    ],
}

MODULE_COMMANDS = {
    "pulseaudio": "audio", "wireplumber": "audio", "pulseaudio/slider": "audio",
    "sndio": "audio", "jack": "audio", "cava": "audio",
    "backlight": "backlight", "backlight/slider": "backlight",
    "mpris": "media", "mpd": "media",
    "network": "network", "wwan": "network",
    "bluetooth": "bluetooth",
    "cpu": "system", "memory": "system", "disk": "system", "load": "system",
    "temperature": "system", "cpu_graph": "system",
    "clock": "clock",
    "battery": "power", "upower": "power", "power-profiles-daemon": "power",
}


def installed(command):
    try:
        program = shlex.split(command)[0]
    except (ValueError, IndexError):
        return False
    return shutil.which(program) is not None


def command_suggestions(module):
    term = terminal()
    group = MODULE_COMMANDS.get(module)
    groups = ([group] if group else []) + (["launcher"] if group != "launcher" else [])

    sections = []
    for name in groups:
        items = []
        for command, label in COMMANDS[name]:
            if "{term}" in command:
                if not term:
                    continue
                program = command.split()[1]
                if not shutil.which(program):
                    continue
                command = command.replace("{term}", term)
            elif not installed(command):
                continue
            items.append(Suggestion(command, label, command))
        if items:
            title = "For this module" if name == group else "Useful commands"
            sections.append(Section(title, items))
    return sections


# ---------------------------------------------------------------- system

def read(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return ""


def timezones():
    zones = []
    for line in read("/usr/share/zoneinfo/zone1970.tab").splitlines():
        if line and not line.startswith("#"):
            zones.append(line.split("\t")[2])
    zones.sort()
    current = os.path.realpath("/etc/localtime").partition("zoneinfo/")[2]
    items = [Suggestion(z, z) for z in zones]
    sections = []
    if current:
        sections.append(Section("Your time zone", [Suggestion(current, current)]))
    sections.append(Section("All time zones", items))
    return sections


def locales():
    try:
        output = subprocess.run(["locale", "-a"], capture_output=True, text=True).stdout
    except OSError:
        return []
    names = [n for n in output.split() if n.lower().endswith((".utf8", ".utf-8"))]
    # Waybar wants "it_IT.UTF-8" style names.
    items = [Suggestion(n.rsplit(".", 1)[0] + ".UTF-8") for n in names]
    current = os.environ.get("LC_TIME") or os.environ.get("LANG")
    sections = []
    if current:
        sections.append(Section("Your language", [Suggestion(current)]))
    sections.append(Section("Installed languages", items))
    return sections


def outputs():
    items = []
    for connector in sorted(Path("/sys/class/drm").glob("card*-*")):
        if read(connector / "status") == "connected":
            name = connector.name.split("-", 1)[1]
            items.append(Suggestion(name, name, "Connected screen"))
    items.append(Suggestion("!" + items[0].value if items else "!HDMI-A-1",
                            description="'!' means every screen except this one"))
    return [Section("Screens", items)]


def interfaces():
    items = []
    for interface in sorted(Path("/sys/class/net").iterdir()):
        if interface.name == "lo":
            continue
        wireless = (interface / "wireless").exists()
        items.append(Suggestion(interface.name, interface.name,
                                "Wi-Fi" if wireless else "Wired / other"))
    items += [Suggestion("wl*", "wl*", "Any Wi-Fi card"),
              Suggestion("en*", "en*", "Any wired card")]
    return [Section("Network cards", items)]


def power_supplies(wanted):
    items = []
    for supply in sorted(Path("/sys/class/power_supply").glob("*")):
        if read(supply / "type") == wanted:
            items.append(Suggestion(supply.name, supply.name, read(supply / "model_name")))
    return [Section("Found on this computer", items)] if items else []


def backlights():
    items = [Suggestion(d.name) for d in sorted(Path("/sys/class/backlight").glob("*"))]
    return [Section("Found on this computer", items)] if items else []


def hwmon_paths():
    items = []
    for sensor in sorted(Path("/sys/class/hwmon").glob("hwmon*/temp*_input")):
        name = read(sensor.parent / "name")
        label = read(sensor.with_name(sensor.name.replace("_input", "_label")))
        items.append(Suggestion(str(sensor), f"{name} {label}".strip(), str(sensor)))
    return [Section("Temperature sensors", items)] if items else []


def icon_themes():
    names = set()
    for base in (Path.home() / ".local/share/icons", Path("/usr/share/icons")):
        if base.is_dir():
            names.update(d.name for d in base.iterdir() if (d / "index.theme").exists())
    return [Section("Installed icon themes", [Suggestion(n) for n in sorted(names)])]


def players():
    try:
        output = subprocess.run(["playerctl", "-l"], capture_output=True, text=True,
                                timeout=2).stdout
    except (OSError, subprocess.TimeoutExpired):
        output = ""
    items = [Suggestion("playerctld", "playerctld", "The player you used last")]
    items += [Suggestion(p) for p in output.split()]
    return [Section("Players", items)]


SYSTEM = {
    "timezone": timezones,
    "locale": locales,
    "output": outputs,
    "interface": interfaces,
    "device": backlights,
    "bat": lambda: power_supplies("Battery"),
    "native-path": lambda: power_supplies("Battery"),
    "adapter": lambda: power_supplies("Mains"),
    "hwmon-path": hwmon_paths,
    "icon-theme": icon_themes,
    "player": players,
}


# ---------------------------------------------------------------- entry point

def suggestions(option_kind, module, spec, schema):
    """Sections of suggestions for an option, [] when there are none."""
    sections = []
    if spec.get("presets"):
        sections.append(Section("Ready-made", [
            Suggestion(p["value"], p["label"], p["value"]) for p in spec["presets"]
        ]))

    if option_kind == "format" and schema and schema.get("placeholders"):
        sections.append(Section("Insert a placeholder", [
            Suggestion(p["token"], p["token"], p["description"], insert=True)
            for p in schema["placeholders"]
        ]))
    elif option_kind == "command":
        sections += command_suggestions(module)
    elif option_kind == "ellipsis":
        sections.append(Section("Common", [Suggestion("…"), Suggestion("..."),
                                           Suggestion("", "Nothing")]))
    elif option_kind == "return-type":
        sections.append(Section("Script output", [
            Suggestion("", "Plain text", "Each line of output is a new text"),
            Suggestion("json", "JSON", "The script prints {\"text\": …, \"tooltip\": …}"),
        ]))
    elif option_kind in SYSTEM:
        try:
            sections += SYSTEM[option_kind]()
        except OSError:
            pass
    return sections
