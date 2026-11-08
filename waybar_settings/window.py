import copy

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk

from .config import (load_config, used_modules, save_config, first_bar,
                     find_config_path, user_config_file, user_style_file, DIR_PATH)
from .editor import key_line, open_in_editor
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

        self.stack = Gtk.Stack(hexpand=True, vexpand=True,
                               transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.sidebar = Sidebar(self.stack)

        customize_button = Gtk.Button(label="Customize",
                                      tooltip_text="Edit this part of the config file in vim")
        customize_button.connect("clicked", self.on_customize_clicked)
        apply_button = Gtk.Button(label="Apply", css_classes=["suggested-action"])
        apply_button.connect("clicked", self.on_apply_clicked)
        buttons = Gtk.Box(spacing=6, halign=Gtk.Align.END,
                          margin_top=6, margin_bottom=12, margin_end=12)
        buttons.append(customize_button)
        buttons.append(apply_button)

        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        right_box.append(self.stack)
        right_box.append(buttons)

        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        main_box.append(self.sidebar)
        main_box.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        main_box.append(right_box)

        if self.load():
            self.set_child(main_box)
        self.watch_config()

    # ------------------------------------------------------------ pages

    def load(self, keep_page=None):
        """(Re)build every page from the config on disk."""
        try:
            self.config = load_config()
        except FileNotFoundError as error:
            self.set_child(Gtk.Label(label=f"No configuration found: {error}"))
            return False
        except ValueError as error:
            self.show_message("The config file has an error",
                              f"{error}\n\nFix it with Customize, then come back.")
            if not hasattr(self, "config"):
                self.config = {}
        self.saved = copy.deepcopy(self.config)
        self.bar = first_bar(self.config)

        for page in list(self.stack.get_pages()):
            self.stack.remove(page.get_child())
        self.sidebar.clear()
        self.module_pages = {}  # module name -> stack page name

        self.add_general("layout", "Layout",
                         LayoutPage(self.bar, self.refresh_modules,
                                    lambda: used_modules(self.bar)))
        self.add_general("bar", "Bar", bar_page(self.bar, bar_schema()))
        self.add_general("style", "Style", StylePage())
        self.refresh_modules()

        if not (keep_page and self.stack.get_child_by_name(keep_page)):
            keep_page = "layout"
        self.sidebar.select(keep_page)
        return True

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

    def has_unapplied_changes(self):
        return self.config != self.saved

    # ------------------------------------------------------------ apply

    def on_apply_clicked(self, _button):
        self.apply()

    def apply(self):
        save_config(self.config)
        self.saved = copy.deepcopy(self.config)
        reload_waybar()

    # ------------------------------------------------------------ customize

    def on_customize_clicked(self, _button):
        if not self.has_unapplied_changes():
            self.customize()
            return
        dialog = Gtk.AlertDialog(
            message="You have changes that are not applied yet",
            detail="Apply them before opening the file, or they will be lost.",
            buttons=["Cancel", "Discard", "Apply"],
            cancel_button=0, default_button=2,
        )

        def answered(dialog, result):
            try:
                choice = dialog.choose_finish(result)
            except GLib.Error:
                return
            if choice == 2:
                self.apply()
            elif choice == 1:
                self.load(self.stack.get_visible_child_name())  # back to the file
            if choice in (1, 2):
                self.customize()

        dialog.choose(self, None, answered)

    def customize(self):
        page = self.stack.get_visible_child_name() or "layout"
        if page == "style":
            path, line = user_style_file(), 1
        else:
            path = user_config_file()
            if page == "layout":
                key = "modules-left"
            elif page.startswith("module:"):
                key = page.removeprefix("module:")
            else:  # the bar options are at the top of the file
                key = None
            line = key_line(path, key) if key else 1
        try:
            open_in_editor(path, line)
        except RuntimeError as error:
            self.show_message("Cannot open the editor", str(error))

    # ------------------------------------------------------------ watching

    def watch_config(self):
        """Reload the pages when the config file is changed by another
        program (vim after Customize, for example).
        The folder is watched because vim replaces the file when saving."""
        self.reload_source = None
        DIR_PATH.mkdir(parents=True, exist_ok=True)
        folder = Gio.File.new_for_path(str(DIR_PATH))
        self.monitor = folder.monitor_directory(Gio.FileMonitorFlags.WATCH_MOVES, None)
        self.monitor.connect("changed", self.on_folder_changed)

    def on_folder_changed(self, _monitor, file, other, _event):
        names = {f.get_basename() for f in (file, other) if f}
        if find_config_path().name not in names and "style.css" not in names:
            return
        # Several events arrive for one save: wait until they stop.
        if self.reload_source:
            GLib.source_remove(self.reload_source)
        self.reload_source = GLib.timeout_add(300, self.on_config_changed_on_disk,
                                              "style.css" in names)

    def on_config_changed_on_disk(self, style_changed):
        self.reload_source = None
        try:
            on_disk = load_config()
        except (OSError, ValueError):
            on_disk = None  # half-written or broken: load() will explain
        if on_disk is not None and on_disk == self.saved:
            if style_changed:
                reload_waybar()
            return False  # our own save, or nothing new
        if self.has_unapplied_changes():
            self.show_message("The config file was changed by another program",
                              "Your changes here were kept. Press Apply to save them "
                              "over the file, or close the app to keep the file.")
            return False
        self.load(self.stack.get_visible_child_name())
        reload_waybar()
        return False

    def show_message(self, message, detail):
        Gtk.AlertDialog(message=message, detail=detail).show(self)
