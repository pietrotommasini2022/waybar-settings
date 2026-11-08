"""Choose which modules are in the left, center and right part of the bar."""

import re

from gi.repository import Gdk, GLib, Gtk, Pango

from ..config import COLUMNS
from ..schemas import NAMED_MODULES, available_modules, display_title, picker_title

COLUMN_TITLES = {
    "modules-left": "Left",
    "modules-center": "Center",
    "modules-right": "Right",
}

NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class ModulePicker(Gtk.Popover):
    """Searchable list of all modules. Calls on_pick(module_name)."""

    def __init__(self, used, on_pick):
        super().__init__()
        self.used = used
        self.on_pick = on_pick
        self.named_prefix = None

        self.pages = Gtk.Stack(transition_type=Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)

        # Page 1: the list of modules.
        list_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.search = Gtk.SearchEntry(placeholder_text="Search modules")
        self.search.connect("search-changed", lambda _e: self.list_box.invalidate_filter())
        self.search.connect("activate", self.on_search_activate)
        list_page.append(self.search)

        self.list_box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE,
                                    css_classes=["rich-list"])
        self.list_box.set_filter_func(self.filter_row)
        self.list_box.connect("row-activated", self.on_row_activated)
        for schema in available_modules():
            self.list_box.append(self.module_row(schema))

        scroll = Gtk.ScrolledWindow(min_content_width=320, min_content_height=360,
                                    hscrollbar_policy=Gtk.PolicyType.NEVER)
        scroll.set_child(self.list_box)
        list_page.append(scroll)
        self.pages.add_named(list_page, "list")

        # Page 2: name for custom/… and group/… modules.
        name_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.name_title = Gtk.Label(xalign=0, css_classes=["heading"])
        name_page.append(self.name_title)
        name_page.append(Gtk.Label(label="Give it a short name (letters, numbers, - and _).",
                                   xalign=0, wrap=True, css_classes=["dim-label"]))
        self.name_entry = Gtk.Entry()
        self.name_entry.connect("changed", self.on_name_changed)
        self.name_entry.connect("activate", self.on_name_confirm)
        name_page.append(self.name_entry)
        buttons = Gtk.Box(spacing=6, halign=Gtk.Align.END)
        back = Gtk.Button(label="Back")
        back.connect("clicked", lambda _b: self.pages.set_visible_child_name("list"))
        self.add_button = Gtk.Button(label="Add", sensitive=False, css_classes=["suggested-action"])
        self.add_button.connect("clicked", self.on_name_confirm)
        buttons.append(back)
        buttons.append(self.add_button)
        name_page.append(buttons)
        self.pages.add_named(name_page, "name")

        self.set_child(self.pages)
        self.connect("show", self.on_show)

    def module_row(self, schema):
        row = Gtk.ListBoxRow()
        row.module = schema["module"]
        row.search_text = f"{schema['module']} {picker_title(schema['module'])}".lower()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2,
                      margin_top=6, margin_bottom=6, margin_start=6, margin_end=6)
        box.append(Gtk.Label(label=picker_title(schema["module"]), xalign=0))
        box.append(Gtk.Label(label=schema["description"], xalign=0, wrap=True,
                             max_width_chars=40, css_classes=["dim-label", "caption"]))
        row.set_child(box)
        return row

    def filter_row(self, row):
        # Modules can appear only once, except those with a custom name.
        if row.module in self.used() and row.module not in NAMED_MODULES:
            return False
        text = self.search.get_text().strip().lower()
        return all(word in row.search_text for word in text.split())

    def on_show(self, _popover):
        self.search.set_text("")
        self.pages.set_visible_child_name("list")
        self.list_box.invalidate_filter()
        self.search.grab_focus()

    def on_search_activate(self, _entry):
        row = next((r for r in self.rows() if r.get_child_visible()), None)
        if row:
            self.on_row_activated(self.list_box, row)

    def rows(self):
        row = self.list_box.get_first_child()
        while row:
            yield row
            row = row.get_next_sibling()

    def on_row_activated(self, _list_box, row):
        if row.module in NAMED_MODULES:
            self.named_prefix = row.module
            self.name_title.set_label(picker_title(row.module))
            self.name_entry.set_text("")
            self.pages.set_visible_child_name("name")
            self.name_entry.grab_focus()
            return
        self.pick(row.module)

    def named_module(self):
        return f"{self.named_prefix}/{self.name_entry.get_text().strip()}"

    def on_name_changed(self, entry):
        name = entry.get_text().strip()
        valid = bool(NAME_RE.match(name)) and self.named_module() not in self.used()
        self.add_button.set_sensitive(valid)

    def on_name_confirm(self, _widget):
        if self.add_button.get_sensitive():
            self.pick(self.named_module())

    def pick(self, module):
        self.popdown()
        self.on_pick(module)


class LayoutPage(Gtk.Box):
    """Three editable columns. Calls on_changed() after every change."""

    def __init__(self, config, on_changed, used_modules):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=18,
                         margin_top=18, margin_bottom=18, margin_start=18, margin_end=18)
        self.config = config
        self.on_changed = on_changed
        self.used_modules = used_modules

        self.append(Gtk.Label(label="Layout", xalign=0, css_classes=["title-2"]))
        self.append(Gtk.Label(
            label="Choose the modules shown in each part of the bar. "
                  "Each module you add gets its own page in the sidebar.",
            xalign=0, wrap=True))

        columns = Gtk.Box(spacing=12, homogeneous=True)
        self.lists = {}
        for column in COLUMNS:
            columns.append(self.column(column))
        self.append(columns)

        self.refresh()

    def column(self, column):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.append(Gtk.Label(label=COLUMN_TITLES[column], xalign=0, css_classes=["heading"]))

        list_box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["rich-list"])
        list_box.set_placeholder(Gtk.Label(label="Empty", css_classes=["dim-label"],
                                           margin_top=12, margin_bottom=12))
        self.lists[column] = list_box
        # Dropping on the empty part of a column adds the module at the end.
        drop = Gtk.DropTarget.new(str, Gdk.DragAction.MOVE)
        drop.connect("drop", lambda _t, value, _x, _y: self.on_drop(
            value, column, len(self.config.get(column, []))))
        list_box.add_controller(drop)
        frame = Gtk.Frame()
        frame.set_child(list_box)
        box.append(frame)

        add = Gtk.MenuButton(label="Add module", halign=Gtk.Align.START)
        add.set_popover(ModulePicker(self.used_modules,
                                     lambda module: self.add(column, module)))
        box.append(add)
        return box

    # ------------------------------------------------------------ changes

    def modules(self, column):
        return self.config.setdefault(column, [])

    def add(self, column, module):
        self.modules(column).append(module)
        self.changed()

    def remove(self, column, index):
        del self.modules(column)[index]
        self.changed()

    def move(self, column, index, offset):
        modules = self.modules(column)
        modules.insert(index + offset, modules.pop(index))
        self.changed()

    def move_to(self, column, index, target):
        module = self.modules(column).pop(index)
        self.modules(target).append(module)
        self.changed()

    def changed(self):
        self.refresh()
        self.on_changed()

    # ------------------------------------------------------------ widgets

    def refresh(self):
        for column, list_box in self.lists.items():
            list_box.remove_all()
            modules = self.config.get(column, [])
            for index, module in enumerate(modules):
                list_box.append(self.module_row(column, index, module, len(modules)))

    def module_row(self, column, index, module, count):
        box = Gtk.Box(spacing=4, margin_top=4, margin_bottom=4, margin_start=8, margin_end=4)

        handle = Gtk.Image(icon_name="list-drag-handle-symbolic", css_classes=["dim-label"])
        box.append(handle)

        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True,
                         valign=Gtk.Align.CENTER)
        labels.append(Gtk.Label(label=display_title(module), xalign=0, wrap=True,
                                wrap_mode=Pango.WrapMode.WORD_CHAR))
        labels.append(Gtk.Label(label=module, xalign=0, wrap=True,
                                wrap_mode=Pango.WrapMode.WORD_CHAR,
                                css_classes=["dim-label", "caption"]))
        box.append(labels)

        # Actions in a small menu; reordering is also possible by dragging.
        menu = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        popover = Gtk.Popover(child=menu)

        def action(label, callback, sensitive=True, css_classes=()):
            button = Gtk.Button(label=label, has_frame=False, sensitive=sensitive,
                                css_classes=list(css_classes))
            label_widget = button.get_child()
            label_widget.set_xalign(0)
            button.connect("clicked", lambda _b: (popover.popdown(), callback()))
            menu.append(button)

        action("Move up", lambda: self.move(column, index, -1), index > 0)
        action("Move down", lambda: self.move(column, index, 1), index < count - 1)
        for target in COLUMNS:
            if target != column:
                action(f"Move to {COLUMN_TITLES[target]}",
                       lambda t=target: self.move_to(column, index, t))
        menu.append(Gtk.Separator(margin_top=4, margin_bottom=4))
        action("Remove", lambda: self.remove(column, index), css_classes=["error"])

        box.append(Gtk.MenuButton(icon_name="view-more-symbolic", popover=popover,
                                  has_frame=False, valign=Gtk.Align.CENTER,
                                  tooltip_text="Move or remove"))

        row = Gtk.ListBoxRow(activatable=False, child=box)
        row.set_tooltip_text("Drag to move")

        drag = Gtk.DragSource(actions=Gdk.DragAction.MOVE)
        drag.connect("prepare", lambda _s, _x, _y: Gdk.ContentProvider.new_for_value(
            f"{column}\n{index}"))
        drag.connect("drag-begin", lambda s, _d: s.set_icon(
            Gtk.WidgetPaintable.new(row), 0, 0))
        row.add_controller(drag)

        drop = Gtk.DropTarget.new(str, Gdk.DragAction.MOVE)
        # Upper half of the row: insert before it; lower half: after it.
        drop.connect("drop", lambda _t, value, _x, y: self.on_drop(
            value, column, index + (y > row.get_height() / 2)))
        row.add_controller(drop)
        return row

    def on_drop(self, value, column, position):
        source_column, _, source_index = value.partition("\n")
        if source_column not in COLUMNS:
            return False
        source_index = int(source_index)
        if source_column == column and source_index < position:
            position -= 1
        module = self.modules(source_column).pop(source_index)
        self.modules(column).insert(position, module)
        # Rebuild after the drag has finished.
        GLib.idle_add(lambda: self.changed() and False)
        return True
