import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from .config import load_config
from .pages.layout import LayoutPage
from .pages.style import StylePage

class MainWindow(Gtk.ApplicationWindow):

    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("Waybar Settings")
        self.set_default_size(600, 600)
        
        main_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=10
        )

        try:
            config = load_config()
        except FileNotFoundError as error:
            main_box.append(Gtk.Label(label=f"No configuration found: {error}"))
        else:
            main_box.append(LayoutPage(config))
            main_box.append(StylePage())
        self.set_child(
            main_box
        )
        


    