import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from .config import load_config, used_modules
from .pages.layout import LayoutPage
from .pages.style import StylePage
from .pages.module import ModulePage

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
            stack = Gtk.Stack()
            stack.add_titled(LayoutPage(config), "layout", "Layout")
            stack.add_titled(StylePage(), "style", "Style")

            for module in used_modules(config):
                stack.add_titled(ModulePage(name=module), module, module)

            stack.set_hexpand(True)

            sidebar = Gtk.StackSidebar()
            sidebar.set_stack(stack)
            main_box.append(sidebar)
            main_box.append(stack)

        self.set_child(
            main_box
        )
        


    