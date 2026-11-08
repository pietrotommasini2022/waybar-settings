"""Sidebar with two parts: the general pages, then the modules in use."""

from gi.repository import Gtk


class Sidebar(Gtk.Box):
    def __init__(self, stack):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, width_request=200)
        self.stack = stack

        self.general = self.new_list()
        self.append(self.general)

        self.append(Gtk.Separator(margin_top=6, margin_bottom=6))
        self.append(Gtk.Label(label="Modules", xalign=0, margin_start=12, margin_bottom=4,
                              css_classes=["heading", "dim-label"]))

        self.modules = self.new_list()
        self.modules.set_placeholder(Gtk.Label(
            label="No modules yet.\nAdd them in Layout.", justify=Gtk.Justification.CENTER,
            margin_top=12, css_classes=["dim-label"]))
        scroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        scroll.set_child(self.modules)
        self.append(scroll)

    def new_list(self):
        list_box = Gtk.ListBox(css_classes=["navigation-sidebar"])
        list_box.connect("row-selected", self.on_row_selected)
        return list_box

    @staticmethod
    def row(page_name, title):
        row = Gtk.ListBoxRow()
        row.page_name = page_name
        row.set_child(Gtk.Label(label=title, xalign=0))
        return row

    def clear(self):
        self.general.remove_all()
        self.modules.remove_all()

    def add_general(self, page_name, title):
        self.general.append(self.row(page_name, title))

    def set_modules(self, pages):
        """pages: list of (page_name, title). Keeps the selection if possible."""
        selected = self.modules.get_selected_row()
        selected_name = selected.page_name if selected else None
        self.modules.remove_all()
        for page_name, title in pages:
            row = self.row(page_name, title)
            self.modules.append(row)
            if page_name == selected_name:
                self.modules.select_row(row)

    def select(self, page_name):
        for list_box in (self.general, self.modules):
            row = list_box.get_first_child()
            while row:
                if getattr(row, "page_name", None) == page_name:
                    list_box.select_row(row)
                    return
                row = row.get_next_sibling()

    def on_row_selected(self, list_box, row):
        if row is None:
            return
        # Only one row selected across the two lists.
        other = self.modules if list_box is self.general else self.general
        other.unselect_all()
        self.stack.set_visible_child_name(row.page_name)
