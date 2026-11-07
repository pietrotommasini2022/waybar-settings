import gi
import json5
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk
from pathlib import Path

def new_column(title, spacing, modules):
    box = Gtk.Box(
        orientation=Gtk.Orientation.VERTICAL,
        spacing=spacing
    )
    box.append(Gtk.Label(label=title))

    for m in modules:
        subtitle = Gtk.Label(label=m)
        box.append(subtitle)

    return box

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

def on_activate(app):

    config = load_config()
    main = Gtk.Box(
        orientation=Gtk.Orientation.HORIZONTAL,
        spacing=10,
    )
    main.set_homogeneous(True)
    main.append(new_column("Left", 10, config["modules-left"]))
    main.append(new_column("Center", 10, config["modules-center"]))
    main.append(new_column("Right", 10, config["modules-right"]))


    window = Gtk.ApplicationWindow(application=app)
    window.set_title("Waybar Settings")
    window.set_default_size(600, 600)

    window.set_child(
        main
    )

    window.present()

app = Gtk.Application(
    application_id="com.pietrotommasini.WaybarSettings"
)

app.connect("activate", on_activate)

app.run()