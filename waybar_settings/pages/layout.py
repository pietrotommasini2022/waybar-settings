import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

def new_column(title, spacing, modules):
    box = Gtk.Box(
        orientation=Gtk.Orientation.VERTICAL,
        spacing=spacing,
    )
    box.append(Gtk.Label(label=title))

    for module in modules:
        box.append(Gtk.Label(label=module))

    return box

class LayoutPage(Gtk.Box):
    def __init__(self, config):
        super().__init__()

        self.set_homogeneous(True)

        self.append(new_column("Left", 10, config.get("modules-left", [])))
        self.append(new_column("Center", 10, config.get("modules-center", [])))
        self.append(new_column("Right", 10, config.get("modules-right", [])))

