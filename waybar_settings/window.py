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

        stack = Gtk.Stack()
        stack.add_titled(Gtk.Label(LayoutPage(config), "layout", "Layout"))
        stack.add_titled(Gtk.Label(StylePage, "style", "Style"))
        stack.set_hexpand(True)

        sidebar = Gtk.StackSidebar()
        sidebar.set_stack(stack)
        
        main_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=10
        )

        try:
            config = load_config()
        except FileNotFoundError as error:
            main_box.append(Gtk.Label(label=f"No configuration found: {error}"))
        else:
            main_box.append(stack)
            main_box.append(sidebar)
        self.set_child(
            main_box
        )
        


    