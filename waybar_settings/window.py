import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from .config import load_config, used_modules, save_config
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

        right_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=10,
            margin_top=12
        )

        try:
            self.config = load_config()
        except FileNotFoundError as error:
            main_box.append(Gtk.Label(label=f"No configuration found: {error}"))
        else:
            stack = Gtk.Stack()
            stack.add_titled(LayoutPage(self.config), "layout", "Layout")

            for module in used_modules(self.config):
                stack.add_titled(ModulePage(module_name=module, settings=self.config.setdefault(module, {})), module, module)

            stack.add_titled(StylePage(), "style", "Style")

            stack.set_hexpand(True)

            scroll_view = Gtk.ScrolledWindow(vexpand=True)
            scroll_view.set_child(stack)

            sidebar = Gtk.StackSidebar()
            sidebar.set_stack(stack)
            main_box.append(sidebar)
            main_box.append(right_box)
            right_box.append(scroll_view)

            apply_button = Gtk.Button(label="Apply", halign=Gtk.Align.END, margin_bottom=12, margin_end=12)
            apply_button.connect("clicked", self.on_apply_clicked)

            right_box.append(apply_button)
            

        self.set_child(
            main_box
        )
    
    def on_apply_clicked(self, button):
        save_config(self.config)
        


    