"""Open a file in vim, inside a terminal, at a given line."""

import os
import re
import shlex
import shutil
import subprocess

EDITOR = "vim"

# Terminal emulators and the arguments that come before the command to run.
TERMINALS = [
    ("xdg-terminal-exec", []),
    ("kitty", []),
    ("foot", []),
    ("ghostty", ["-e"]),
    ("alacritty", ["-e"]),
    ("wezterm", ["start", "--"]),
    ("gnome-terminal", ["--"]),
    ("konsole", ["-e"]),
    ("xfce4-terminal", ["-x"]),
    ("xterm", ["-e"]),
]


def find_terminal():
    """Return the command that runs a program in a terminal, or None.
    $TERMINAL wins over the list above."""
    wanted = os.environ.get("TERMINAL")
    if wanted:
        parts = shlex.split(wanted)
        if parts and shutil.which(parts[0]):
            known = dict(TERMINALS).get(os.path.basename(parts[0]))
            return parts + (known if known is not None else ["-e"])
    for program, args in TERMINALS:
        if shutil.which(program):
            return [program] + args
    return None


def key_line(path, key):
    """1-based line where `key` is defined as "key": … in the file,
    or where it is first mentioned, or 1."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return 1
    quoted = '"' + key + '"'
    definition = re.compile(re.escape(quoted) + r"\s*:")
    for number, line in enumerate(lines, 1):
        if definition.search(line):
            return number
    for number, line in enumerate(lines, 1):
        if quoted in line:
            return number
    return 1


def open_in_editor(path, line=1):
    """Start vim in a terminal. Raises RuntimeError with a readable message."""
    if not shutil.which(EDITOR):
        raise RuntimeError(f"{EDITOR} is not installed.")
    terminal = find_terminal()
    if terminal is None:
        raise RuntimeError("No terminal emulator found. Set the TERMINAL environment "
                           "variable, for example TERMINAL=kitty.")
    subprocess.Popen(terminal + [EDITOR, f"+{line}", str(path)], start_new_session=True)
