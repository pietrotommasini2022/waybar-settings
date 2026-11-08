import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from .config import load_config, used_modules, save_config, first_bar
from .pages.layout import LayoutPage
from .pages.style import StylePage
from .pages.module import module_page, bar_page
from .schemas import load_schema, bar_schema, display_title
from .sidebar import Sidebar
from .waybar import reload_waybar


def scrolled(child):
    scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
    scroll.set_child(child)
    return scroll


class MainWindow(Gtk.ApplicationWindow):

    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("Waybar Settings")
        self.set_default_size(950, 700)

        try:
            self.config = load_config()
        except FileNotFoundError as error:
            self.set_child(Gtk.Label(label=f"No configuration found: {error}"))
            return

        self.bar = first_bar(self.config)
        self.module_pages = {}  # module name -> stack page name

        self.stack = Gtk.Stack(hexpand=True, vexpand=True,
                               transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.sidebar = Sidebar(self.stack)

        self.add_general("layout", "Layout",
                         LayoutPage(self.bar, self.refresh_modules,
                                    lambda: used_modules(self.bar)))
        self.add_general("bar", "Bar", bar_page(self.bar, bar_schema()))
        self.add_general("style", "Style", StylePage())
        self.refresh_modules()
        self.sidebar.select("layout")

        apply_button = Gtk.Button(label="Apply", halign=Gtk.Align.END,
                                  margin_top=6, margin_bottom=12, margin_end=12,
                                  css_classes=["suggested-action"])
        apply_button.connect("clicked", self.on_apply_clicked)

        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        right_box.append(self.stack)
        right_box.append(apply_button)

        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        main_box.append(self.sidebar)
        main_box.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        main_box.append(right_box)
        self.set_child(main_box)

    def add_general(self, name, title, page):
        self.stack.add_named(scrolled(page), name)
        self.sidebar.add_general(name, title)

    def refresh_modules(self):
        """Create a page for each module in use and drop the others.
        Called at startup and whenever the layout changes."""
        modules = used_modules(self.bar)

        for module in list(self.module_pages):
            if module not in modules:
                page_name = self.module_pages.pop(module)
                self.stack.remove(self.stack.get_child_by_name(page_name))

        for module in modules:
            if module not in self.module_pages:
                page_name = f"module:{module}"
                page = module_page(self.bar, module, display_title(module), load_schema(module))
                self.stack.add_named(scrolled(page), page_name)
                self.module_pages[module] = page_name

        self.sidebar.set_modules(
            [(self.module_pages[m], display_title(m)) for m in modules]
        )

    def on_apply_clicked(self, button):
        save_config(self.config)
        reload_waybar()
