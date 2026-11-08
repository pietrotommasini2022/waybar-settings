"""A settings page built from a schema (see schemas/README.md).

Options are split into sections by their "group"; options marked as advanced
go into a collapsed "Advanced" section at the bottom. An option that is not in
the config shows Waybar's default and is written only when the user changes it.
"""

from dataclasses import dataclass, replace
import json
import re

import json5
from gi.repository import GLib, Gtk

from ..config import COLUMNS
from ..schemas import base_name
from ..suggestions import is_path, kind, suggestions

MISSING = object()

# Sections shown first, in this order; the others follow alphabetically.
SECTION_ORDER = [
    "Placement", "Size", "Layout", "Display", "Tooltip", "Calendar",
    "Time zone", "Click & scroll", "Menu", "Drawer", "Windows", "Audio",
    "Script", "Behavior",
]
DEFAULT_SECTION = "General"
ADVANCED_SECTION = "Advanced"


@dataclass(frozen=True)
class Context:
    """What an editor may need to know besides its own option."""
    module: str  # base module name, e.g. "battery"; "bar" for the bar
    schema: dict | None
    key: str = ""

    def with_key(self, key):
        return replace(self, key=key)


class Store:
    """Reads and writes the dictionary at `path` inside `root`.

    Dictionaries along the path are created only when something is written,
    and removed again when they become empty, so that looking at a page never
    changes the config file.
    """

    def __init__(self, root, path=()):
        self.root = root
        self.path = tuple(path)

    def child(self, key):
        return Store(self.root, self.path + (key,))

    def data(self):
        node = self.root
        for key in self.path:
            node = node.get(key) if isinstance(node, dict) else None
            if node is None:
                return {}
        return node if isinstance(node, dict) else {}

    def get(self, key):
        return self.data().get(key, MISSING)

    def set(self, key, value):
        node = self.root
        for part in self.path:
            if not isinstance(node.get(part), dict):
                node[part] = {}
            node = node[part]
        node[key] = value

    def delete(self, key):
        nodes = [self.root]
        for part in self.path:
            node = nodes[-1].get(part)
            if not isinstance(node, dict):
                return
            nodes.append(node)
        nodes[-1].pop(key, None)
        # Drop the dictionaries that are now empty.
        for parent, part, node in reversed(list(zip(nodes, self.path, nodes[1:]))):
            if node:
                break
            del parent[part]


# ---------------------------------------------------------------- editors
#
# Each editor returns (widget, show) where show(value) displays a value
# without reporting a change. Editors report changes by calling
# on_change(value), or on_change(MISSING) to remove the option.


def _json_text(value):
    return json.dumps(value, ensure_ascii=False)


def json_editor(spec, value, on_change):
    """Fallback for lists, objects and values of an unexpected type."""
    entry = Gtk.Entry(width_chars=24, valign=Gtk.Align.CENTER)
    default = spec.get("default")
    if spec.get("default_note"):
        entry.set_placeholder_text(spec["default_note"])
    elif default is not None:
        entry.set_placeholder_text(_json_text(default))

    def show(value):
        entry.set_text("" if value is MISSING else _json_text(value))
        entry.remove_css_class("error")

    def changed(entry):
        text = entry.get_text().strip()
        if not text:
            entry.remove_css_class("error")
            on_change(MISSING)
            return
        try:
            parsed = json5.loads(text)
        except ValueError:
            entry.add_css_class("error")
            return
        entry.remove_css_class("error")
        on_change(parsed)

    show(value)
    entry.connect("changed", changed)
    entry.set_tooltip_text("Value in JSON, for example [\"a\", \"b\"] or {\"key\": 1}")
    return entry, show


class SuggestionPopover(Gtk.Popover):
    """Menu with the suggested values of a text option (see suggestions.py).
    Recomputed every time it opens, so system lists stay current."""

    def __init__(self, entry, option_kind, spec, context):
        super().__init__()
        self.entry = entry
        self.option_kind = option_kind
        self.spec = spec
        self.context = context

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.search = Gtk.SearchEntry(placeholder_text="Search")
        self.search.connect("search-changed", lambda _e: self.list_box.invalidate_filter())
        box.append(self.search)

        self.list_box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.list_box.set_filter_func(self.filter_row)
        self.list_box.connect("row-activated", self.on_activated)
        self.list_box.set_placeholder(Gtk.Label(label="Nothing found on this system",
                                                margin_top=12, margin_bottom=12,
                                                css_classes=["dim-label"]))
        self.scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER,
                                         propagate_natural_height=True,
                                         max_content_height=420, min_content_width=320)
        self.scroll.set_child(self.list_box)
        box.append(self.scroll)
        self.set_child(box)
        self.connect("show", self.on_show)

    def on_show(self, _popover):
        self.list_box.remove_all()
        sections = suggestions(self.option_kind, self.context.module, self.spec,
                               self.context.schema)
        count = 0
        for section_ in sections:
            header = Gtk.ListBoxRow(activatable=False, selectable=False)
            header.suggestion = None
            header.set_child(Gtk.Label(label=section_.title, xalign=0, margin_top=6,
                                       margin_start=6, css_classes=["heading"]))
            self.list_box.append(header)
            for item in section_.items:
                self.list_box.append(self.item_row(item))
                count += 1
        self.search.set_text("")
        self.search.set_visible(count > 10)
        if count > 10:
            self.search.grab_focus()

    @staticmethod
    def item_row(item):
        row = Gtk.ListBoxRow()
        row.suggestion = item
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2,
                      margin_top=4, margin_bottom=4, margin_start=6, margin_end=6)
        box.append(Gtk.Label(label=item.label or item.value or "(empty)", xalign=0,
                             wrap=True, max_width_chars=45))
        if item.description and item.description != (item.label or item.value):
            box.append(Gtk.Label(label=item.description, xalign=0, wrap=True,
                                 max_width_chars=45, css_classes=["dim-label", "caption"]))
        row.set_child(box)
        row.search_text = f"{item.value} {item.label} {item.description}".lower()
        return row

    def filter_row(self, row):
        text = self.search.get_text().strip().lower()
        if not text:
            return True
        if row.suggestion is None:  # hide the headers while searching
            return False
        return all(word in row.search_text for word in text.split())

    def on_activated(self, _list_box, row):
        item = row.suggestion
        if item is None:
            return
        self.popdown()
        if item.insert:
            position = self.entry.get_position()
            self.entry.get_buffer().insert_text(position, item.value, -1)
            self.entry.set_position(position + len(item.value))
        else:
            self.entry.set_text(item.value)
        self.entry.grab_focus()


def browse_button(entry):
    button = Gtk.Button(icon_name="document-open-symbolic", tooltip_text="Choose a file")

    def chosen(dialog, result):
        try:
            file = dialog.open_finish(result)
        except GLib.Error:  # cancelled
            return
        if file and file.get_path():
            entry.set_text(file.get_path())

    def clicked(_button):
        dialog = Gtk.FileDialog(title="Choose a file")
        dialog.open(button.get_root(), None, chosen)

    button.connect("clicked", clicked)
    return button


def string_editor(spec, value, on_change, context=None):
    entry = Gtk.Entry(width_chars=24, valign=Gtk.Align.CENTER)
    default = spec.get("default")
    if isinstance(default, str) and default:
        entry.set_placeholder_text(default)
    elif spec.get("default_note"):
        entry.set_placeholder_text(spec["default_note"])

    def show(value):
        entry.set_text("" if value is MISSING else str(value))

    show(value)
    entry.connect("changed", lambda e: on_change(e.get_text()))

    if context is None:
        return entry, show

    option_kind = kind(context.key)
    has_menu = bool(spec.get("presets")) or (
        option_kind is not None
        and not (option_kind == "format" and not (context.schema or {}).get("placeholders"))
    )
    if not has_menu and not is_path(context.key):
        return entry, show

    # Entry and buttons drawn as one control, like a combo box.
    box = Gtk.Box(valign=Gtk.Align.CENTER, css_classes=["linked"])
    box.append(entry)
    if has_menu:
        box.append(Gtk.MenuButton(
            icon_name="pan-down-symbolic", tooltip_text="Suggestions",
            popover=SuggestionPopover(entry, option_kind, spec, context)))
    if is_path(context.key):
        box.append(browse_button(entry))
    return box, show


def boolean_editor(spec, value, on_change):
    switch = Gtk.Switch(valign=Gtk.Align.CENTER)

    def show(value):
        if value is MISSING:
            value = spec.get("default")
        switch.set_active(bool(value))

    show(value)
    switch.connect("notify::active", lambda s, _p: on_change(s.get_active()))
    return switch, show


def number_editor(spec, value, on_change):
    is_integer = spec["type"] == "integer"
    step = spec.get("step", 1 if is_integer else 0.1)
    digits = 0 if is_integer else max(0, len(f"{step}".partition(".")[2].rstrip("0")))
    spin = Gtk.SpinButton.new_with_range(
        spec.get("min", -100000), spec.get("max", 100000), step
    )
    spin.set_digits(digits)
    spin.set_width_chars(6)
    spin.set_valign(Gtk.Align.CENTER)

    # Without a default ("Empty means no limit") the box stays empty until
    # the user picks a number, instead of showing a misleading 0.
    default = spec.get("default")
    state = {"empty": False}

    def output(spin):
        if state["empty"]:
            spin.set_text("")
            return True
        return False

    def show(value):
        if value is MISSING:
            value = default
        state["empty"] = not isinstance(value, (int, float))
        spin.set_value(value if not state["empty"] else max(spec.get("min", 0), 0))
        spin.update()

    def changed(spin):
        state["empty"] = False
        number = spin.get_value()
        on_change(int(number) if is_integer or number.is_integer() else round(number, digits))

    spin.connect("output", output)
    show(value)
    spin.connect("value-changed", changed)

    if not spec.get("unit"):
        return spin, show
    box = Gtk.Box(spacing=6, valign=Gtk.Align.CENTER)
    box.append(spin)
    box.append(Gtk.Label(label=spec["unit"], css_classes=["dim-label"]))
    return box, show


def enum_editor(spec, value, on_change):
    values = [option["value"] for option in spec["options"]]
    labels = [option["label"] for option in spec["options"]]
    has_unset = spec.get("default") is None
    if has_unset:
        values.insert(0, MISSING)
        labels.insert(0, "Not set")
    # Keep a value from the config even if the schema does not know it.
    if value is not MISSING and value not in values:
        values.append(value)
        labels.append(str(value))

    dropdown = Gtk.DropDown.new_from_strings(labels)
    dropdown.set_valign(Gtk.Align.CENTER)

    def show(value):
        if value is MISSING and not has_unset:
            value = spec.get("default")
        dropdown.set_selected(values.index(value) if value in values else 0)

    show(value)
    dropdown.connect("notify::selected", lambda d, _p: on_change(values[d.get_selected()]))
    return dropdown, show


EDITORS = {
    "string": string_editor,
    "boolean": boolean_editor,
    "integer": number_editor,
    "number": number_editor,
    "enum": enum_editor,
}

TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "enum": lambda v: True,
}


def create_editor(spec, value, on_change, context=None):
    kind = spec.get("type")
    editor = EDITORS.get(kind)
    # A value of another type (see "also_accepts") is edited as JSON.
    if editor is None or (value is not MISSING and not TYPE_CHECKS[kind](value)):
        editor = json_editor
    if editor is string_editor:
        return string_editor(spec, value, on_change, context)
    return editor(spec, value, on_change)


# ---------------------------------------------------------------- rows


def title_box(label, description=None, doc=None):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True,
                  valign=Gtk.Align.CENTER)
    title = Gtk.Label(label=label, xalign=0, wrap=True)
    if doc:
        title.set_tooltip_text(doc)
    box.append(title)
    if description:
        box.append(Gtk.Label(label=description, xalign=0, wrap=True,
                             css_classes=["dim-label", "caption"]))
    return box


class SettingRow(Gtk.ListBoxRow):
    def __init__(self, store, key, spec, context=None):
        super().__init__(activatable=False, selectable=False)
        self.store = store
        self.key = key
        self.updating = False

        box = Gtk.Box(spacing=12, margin_top=8, margin_bottom=8, margin_start=12, margin_end=12)
        box.append(title_box(spec.get("label", key),
                             spec.get("description") or spec.get("doc"),
                             spec.get("doc")))

        value = store.get(key)
        editor, self.show = create_editor(
            spec, value, self.on_change,
            context.with_key(key) if context else None)
        box.append(editor)

        self.reset = Gtk.Button(icon_name="edit-undo-symbolic", valign=Gtk.Align.CENTER,
                                has_frame=False, tooltip_text="Back to the default")
        self.reset.connect("clicked", self.on_reset)
        self.reset.set_opacity(0 if value is MISSING else 1)
        self.reset.set_sensitive(value is not MISSING)
        box.append(self.reset)

        self.set_child(box)

    def on_change(self, value):
        if self.updating:
            return
        if value is MISSING:
            self.store.delete(self.key)
        else:
            self.store.set(self.key, value)
        self.update_reset()

    def on_reset(self, _button):
        self.store.delete(self.key)
        self.updating = True
        self.show(MISSING)
        self.updating = False
        self.update_reset()

    def update_reset(self):
        is_set = self.store.get(self.key) is not MISSING
        self.reset.set_opacity(1 if is_set else 0)
        self.reset.set_sensitive(is_set)


class ObjectRow(Gtk.ListBoxRow):
    """An option with its own options (e.g. clock -> calendar)."""

    def __init__(self, store, key, spec, context=None):
        super().__init__(activatable=False, selectable=False)
        expander = Gtk.Expander(margin_top=8, margin_bottom=8, margin_start=12, margin_end=12)
        expander.set_label_widget(title_box(spec.get("label", key), spec.get("description")))

        child_store = store.child(key)
        list_box = settings_list(child_store, spec["settings"].items(), context)
        list_box.set_margin_top(8)
        expander.set_child(list_box)
        self.set_child(expander)


def settings_list(store, items, context=None):
    list_box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["rich-list"])
    for key, spec in items:
        if spec.get("type") == "object" and "settings" in spec:
            list_box.append(ObjectRow(store, key, spec, context))
        else:
            list_box.append(SettingRow(store, key, spec, context))
    return list_box


def section(title, store, items, context=None):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    box.append(Gtk.Label(label=title, xalign=0, css_classes=["heading"]))
    frame = Gtk.Frame()
    frame.set_child(settings_list(store, items, context))
    box.append(frame)
    return box


def pattern_regex(pattern):
    """'format-<state>' -> regex matching 'format-warning'."""
    parts = re.split(r"<[^>]+>", pattern)
    return re.compile("^" + ".+".join(re.escape(p) for p in parts) + "$")


def section_key(name):
    if name in SECTION_ORDER:
        return (0, SECTION_ORDER.index(name), "")
    return (1, 0, name)


# ---------------------------------------------------------------- page


class SettingsPage(Gtk.Box):
    """Page for a module (or for the bar) described by `schema`.

    `store` points to the dictionary that holds the options.
    `show_unknown` adds an "Other settings" section with the options found in
    the config that the schema does not describe.
    """

    def __init__(self, title, schema, store, module, show_unknown=True):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=18,
                         margin_top=18, margin_bottom=18, margin_start=18, margin_end=18)

        self.append(self.header(title, schema))
        context = Context(module, schema)

        settings = schema["settings"] if schema else {}
        sections = {}
        advanced = []
        for key, spec in settings.items():
            group = spec.get("group") or DEFAULT_SECTION
            if spec.get("advanced") or group == ADVANCED_SECTION:
                advanced.append((key, spec))
            else:
                sections.setdefault(group, []).append((key, spec))

        for name in sorted(sections, key=section_key):
            self.append(section(name, store, sections[name], context))

        if show_unknown:
            unknown = self.unknown_settings(store, settings, schema)
            if unknown:
                self.append(section("Other settings", store, unknown, context))

        if advanced:
            expander = Gtk.Expander(label="Advanced")
            expander.get_label_widget().add_css_class("heading")
            inner = Gtk.Frame(margin_top=6)
            inner.set_child(settings_list(store, advanced, context))
            expander.set_child(inner)
            self.append(expander)

    def header(self, title, schema):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.append(Gtk.Label(label=title, xalign=0, css_classes=["title-2"]))
        if not schema:
            box.append(Gtk.Label(label="There is no description for this module yet: "
                                       "its options are shown as they are in the config.",
                                 xalign=0, wrap=True, css_classes=["dim-label"]))
            return box

        box.append(Gtk.Label(label=schema["description"], xalign=0, wrap=True))
        if schema.get("manual"):
            box.append(Gtk.Label(label=f"Full documentation: man {schema['manual']}",
                                 xalign=0, css_classes=["dim-label", "caption"]))

        placeholders = schema.get("placeholders")
        if placeholders:
            expander = Gtk.Expander(label="Placeholders you can use in the formats")
            grid = Gtk.Grid(column_spacing=12, row_spacing=4, margin_top=6, margin_start=12)
            for row, placeholder in enumerate(placeholders):
                token = Gtk.Label(label=placeholder["token"], xalign=0, selectable=True,
                                  valign=Gtk.Align.START, css_classes=["monospace"])
                grid.attach(token, 0, row, 1, 1)
                grid.attach(Gtk.Label(label=placeholder["description"], xalign=0, wrap=True,
                                      hexpand=True), 1, row, 1, 1)
            expander.set_child(grid)
            box.append(expander)
        return box

    @staticmethod
    def unknown_settings(store, settings, schema):
        patterns = [(pattern_regex(p["pattern"]), p) for p in (schema or {}).get("patterns", [])]
        items = []
        for key, value in store.data().items():
            if key in settings:
                continue
            spec = {"label": key, "type": "json"}
            for regex, pattern in patterns:
                if regex.match(key):
                    spec["description"] = pattern["description"]
                    break
            if isinstance(value, bool):
                spec["type"] = "boolean"
            elif isinstance(value, (int, float)):
                spec["type"] = "integer" if isinstance(value, int) else "number"
            elif isinstance(value, str):
                spec["type"] = "string"
            items.append((key, spec))
        return items


def module_page(config, module, title, schema):
    return SettingsPage(title, schema, Store(config, [module]), base_name(module))


def bar_page(config, schema):
    # The bar's options live at the top level of the config, next to the
    # columns and the modules: show only the ones the schema describes.
    settings = {k: v for k, v in schema["settings"].items() if k not in COLUMNS}
    return SettingsPage(schema["title"], {**schema, "settings": settings},
                        Store(config), "bar", show_unknown=False)
