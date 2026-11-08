"""A settings page built from a schema (see schemas/README.md).

Options are split into sections by their "group"; options marked as advanced
go into a collapsed "Advanced" section at the bottom. An option that is not in
the config shows Waybar's default and is written only when the user changes it.
"""

import json
import re

import json5
from gi.repository import Gtk

from ..config import COLUMNS

MISSING = object()

# Sections shown first, in this order; the others follow alphabetically.
SECTION_ORDER = [
    "Placement", "Size", "Layout", "Display", "Tooltip", "Calendar",
    "Time zone", "Click & scroll", "Menu", "Drawer", "Windows", "Audio",
    "Script", "Behavior",
]
DEFAULT_SECTION = "General"
ADVANCED_SECTION = "Advanced"


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


def string_editor(spec, value, on_change):
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

    presets = spec.get("presets")
    if not presets:
        return entry, show

    box = Gtk.Box(spacing=4, valign=Gtk.Align.CENTER)
    box.append(entry)

    popover = Gtk.Popover()
    preset_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    for preset in presets:
        button = Gtk.Button(label=preset["label"], has_frame=False)
        button.set_tooltip_text(preset["value"])

        def pick(_button, preset_value=preset["value"]):
            entry.set_text(preset_value)  # emits "changed"
            popover.popdown()

        button.connect("clicked", pick)
        preset_list.append(button)
    popover.set_child(preset_list)

    menu = Gtk.MenuButton(icon_name="view-more-symbolic", popover=popover)
    menu.set_tooltip_text("Ready-made values")
    box.append(menu)
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


def create_editor(spec, value, on_change):
    kind = spec.get("type")
    editor = EDITORS.get(kind)
    # A value of another type (see "also_accepts") is edited as JSON.
    if editor is None or (value is not MISSING and not TYPE_CHECKS[kind](value)):
        editor = json_editor
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
    def __init__(self, store, key, spec):
        super().__init__(activatable=False, selectable=False)
        self.store = store
        self.key = key
        self.updating = False

        box = Gtk.Box(spacing=12, margin_top=8, margin_bottom=8, margin_start=12, margin_end=12)
        box.append(title_box(spec.get("label", key),
                             spec.get("description") or spec.get("doc"),
                             spec.get("doc")))

        value = store.get(key)
        editor, self.show = create_editor(spec, value, self.on_change)
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

    def __init__(self, store, key, spec):
        super().__init__(activatable=False, selectable=False)
        expander = Gtk.Expander(margin_top=8, margin_bottom=8, margin_start=12, margin_end=12)
        expander.set_label_widget(title_box(spec.get("label", key), spec.get("description")))

        child_store = store.child(key)
        list_box = settings_list(child_store, spec["settings"].items())
        list_box.set_margin_top(8)
        expander.set_child(list_box)
        self.set_child(expander)


def settings_list(store, items):
    list_box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["rich-list"])
    for key, spec in items:
        if spec.get("type") == "object" and "settings" in spec:
            list_box.append(ObjectRow(store, key, spec))
        else:
            list_box.append(SettingRow(store, key, spec))
    return list_box


def section(title, store, items):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    box.append(Gtk.Label(label=title, xalign=0, css_classes=["heading"]))
    frame = Gtk.Frame()
    frame.set_child(settings_list(store, items))
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

    def __init__(self, title, schema, store, show_unknown=True):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=18,
                         margin_top=18, margin_bottom=18, margin_start=18, margin_end=18)

        self.append(self.header(title, schema))

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
            self.append(section(name, store, sections[name]))

        if show_unknown:
            unknown = self.unknown_settings(store, settings, schema)
            if unknown:
                self.append(section("Other settings", store, unknown))

        if advanced:
            expander = Gtk.Expander(label="Advanced")
            expander.get_label_widget().add_css_class("heading")
            inner = Gtk.Frame(margin_top=6)
            inner.set_child(settings_list(store, advanced))
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
    return SettingsPage(title, schema, Store(config, [module]))


def bar_page(config, schema):
    # The bar's options live at the top level of the config, next to the
    # columns and the modules: show only the ones the schema describes.
    settings = {k: v for k, v in schema["settings"].items() if k not in COLUMNS}
    return SettingsPage(schema["title"], {**schema, "settings": settings},
                        Store(config), show_unknown=False)
