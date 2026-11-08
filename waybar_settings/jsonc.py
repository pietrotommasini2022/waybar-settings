"""Edit JSONC text without losing comments or formatting.

    update(text, new_value) -> text

The text is compared with the new value and only the parts that changed are
rewritten: a value is replaced, a key or a list element is added or removed.
Comments, indentation, key order and blank lines stay as they are.

Each change is applied to the text and the text is parsed again before the
next one, so no offsets have to be kept up to date between changes.
"""

from dataclasses import dataclass, field
from difflib import SequenceMatcher
import json
import re

import json5


class ParseError(ValueError):
    pass


# ---------------------------------------------------------------- parser


@dataclass
class Item:
    """An object member ("key": value) or an array element."""
    start: int            # key start for members, value start for elements
    value: "Node"
    key: str | None = None
    comma: int | None = None  # position of the comma after the item

    @property
    def end(self):
        return self.value.end


@dataclass
class Node:
    kind: str             # "object", "array" or "scalar"
    start: int
    end: int              # position after the value
    items: list = field(default_factory=list)

    def item(self, key):
        for item in self.items:
            if item.key == key:
                return item
        return None


NUMBER = re.compile(r"-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?")
LITERAL = re.compile(r"true|false|null")
IDENTIFIER = re.compile(r"[A-Za-z_$][\w$-]*")


class Parser:
    def __init__(self, text):
        self.text = text
        self.pos = 0

    def error(self, message):
        line = self.text.count("\n", 0, self.pos) + 1
        raise ParseError(f"{message} at line {line}")

    def skip(self):
        """Skip whitespace and comments."""
        text = self.text
        while self.pos < len(text):
            char = text[self.pos]
            if char in " \t\r\n﻿":
                self.pos += 1
            elif text.startswith("//", self.pos):
                newline = text.find("\n", self.pos)
                self.pos = len(text) if newline == -1 else newline
            elif text.startswith("/*", self.pos):
                close = text.find("*/", self.pos + 2)
                if close == -1:
                    self.error("Unclosed comment")
                self.pos = close + 2
            else:
                break

    def parse(self):
        self.skip()
        node = self.value()
        self.skip()
        if self.pos != len(self.text):
            self.error("Unexpected text")
        return node

    def value(self):
        if self.pos >= len(self.text):
            self.error("Unexpected end of file")
        char = self.text[self.pos]
        if char == "{":
            return self.container("object", "}")
        if char == "[":
            return self.container("array", "]")
        if char == '"':
            start = self.pos
            self.string()
            return Node("scalar", start, self.pos)
        for pattern in (NUMBER, LITERAL):
            match = pattern.match(self.text, self.pos)
            if match:
                self.pos = match.end()
                return Node("scalar", match.start(), match.end())
        self.error(f"Unexpected character {char!r}")

    def string(self):
        text = self.text
        start = self.pos
        self.pos += 1
        while self.pos < len(text):
            char = text[self.pos]
            if char == "\\":
                self.pos += 2
            elif char == '"':
                self.pos += 1
                return json.loads(text[start:self.pos])
            elif char == "\n":
                break
            else:
                self.pos += 1
        self.error("Unclosed string")

    def key(self):
        if self.text.startswith('"', self.pos):
            return self.string()
        match = IDENTIFIER.match(self.text, self.pos)
        if not match:
            self.error("Expected a key")
        self.pos = match.end()
        return match.group()

    def container(self, kind, close):
        node = Node(kind, self.pos, -1)
        self.pos += 1
        while True:
            self.skip()
            if self.text.startswith(close, self.pos):
                self.pos += 1
                node.end = self.pos
                return node
            start = self.pos
            key = None
            if kind == "object":
                key = self.key()
                self.skip()
                if not self.text.startswith(":", self.pos):
                    self.error("Expected ':'")
                self.pos += 1
                self.skip()
            item = Item(start, self.value(), key)
            node.items.append(item)
            self.skip()
            if self.text.startswith(",", self.pos):
                item.comma = self.pos
                self.pos += 1
            elif not self.text.startswith(close, self.pos):
                self.error(f"Expected ',' or '{close}'")


def parse(text):
    return Parser(text).parse()


# ---------------------------------------------------------------- layout helpers


def line_start(text, pos):
    return text.rfind("\n", 0, pos) + 1


def line_end(text, pos):
    end = text.find("\n", pos)
    return len(text) if end == -1 else end


def indent_of(text, pos):
    start = line_start(text, pos)
    return re.match(r"[ \t]*", text[start:]).group()


def starts_line(text, pos):
    return not text[line_start(text, pos):pos].strip()


def indent_unit(text):
    """The indentation step used in the file (4 spaces if unknown)."""
    sizes = sorted({len(m.group(1)) for m in re.finditer(r"\n( +)\S", text)})
    if "\n\t" in text and not sizes:
        return "\t"
    return " " * sizes[0] if sizes else "    "


def item_indent(text, node, unit):
    """Indentation for a new item of `node`."""
    for item in node.items:
        if starts_line(text, item.start):
            return indent_of(text, item.start)
    return indent_of(text, node.start) + unit


def is_multiline(text, node):
    return "\n" in text[node.start:node.end]


def render(value, indent, unit):
    """JSON text for a value, indented to sit at `indent`.
    Short lists and objects of plain values stay on one line."""
    flat = json.dumps(value, ensure_ascii=False)
    if not isinstance(value, (dict, list)) or not value:
        return flat
    children = value.values() if isinstance(value, dict) else value
    if len(flat) + len(indent) <= 80 and not any(isinstance(c, (dict, list)) for c in children):
        return flat
    inner = indent + unit
    if isinstance(value, dict):
        lines = [f"{inner}{json.dumps(k, ensure_ascii=False)}: {render(v, inner, unit)}"
                 for k, v in value.items()]
        return "{\n" + ",\n".join(lines) + "\n" + indent + "}"
    lines = [inner + render(v, inner, unit) for v in value]
    return "[\n" + ",\n".join(lines) + "\n" + indent + "]"


def replace(text, start, end, new):
    return text[:start] + new + text[end:]


# ---------------------------------------------------------------- edits


def find(root, path):
    node = root
    for part in path:
        if isinstance(part, int):
            node = node.items[part].value
        else:
            node = node.item(part).value
    return node


def set_value(text, path, value):
    root = parse(text)
    node = find(root, path)
    unit = indent_unit(text)
    return replace(text, node.start, node.end, render(value, indent_of(text, node.start), unit))


def widen(text, start, end):
    """Extend a deleted range to whole lines when it is alone on its lines
    (a comment at the end of the last line goes with it)."""
    if starts_line(text, start):
        match = re.compile(r"[ \t]*(//[^\n]*)?(\n|$)").match(text, end)
        if match:
            return line_start(text, start), match.end()
    # Inline: also drop the spaces around it.
    while end < len(text) and text[end] in " \t":
        end += 1
    return start, end


def remove_item(text, path):
    root = parse(text)
    node = find(root, path[:-1])
    index = path[-1] if isinstance(path[-1], int) else \
        next(i for i, item in enumerate(node.items) if item.key == path[-1])
    item = node.items[index]

    if item.comma is not None:
        start, end = widen(text, item.start, item.comma + 1)
        return replace(text, start, end, "")

    # Last item without a comma: also drop the comma of the item before it.
    start, end = widen(text, item.start, item.end)
    if not starts_line(text, item.start):
        while start > 0 and text[start - 1] in " \t":
            start -= 1
    text = replace(text, start, end, "")
    if index > 0:
        previous = node.items[index - 1]
        text = replace(text, previous.comma, previous.comma + 1, "")
    return text


def insert_item(text, path, index, key, value):
    """Insert an item at `index` in the container at `path`
    (`key` is None for arrays)."""
    root = parse(text)
    node = find(root, path)
    unit = indent_unit(text)
    items = node.items
    multiline = is_multiline(text, node)
    indent = item_indent(text, node, unit) if multiline else ""
    rendered = render(value, indent, unit)
    new = rendered if key is None else f"{json.dumps(key, ensure_ascii=False)}: {rendered}"

    if not items:
        if multiline:
            return replace(text, node.start + 1, node.start + 1, "\n" + indent + new)
        return replace(text, node.start + 1, node.end - 1, new)

    if index < len(items):
        before = items[index]
        if multiline and starts_line(text, before.start):
            position = line_start(text, before.start)
            return replace(text, position, position, f"{indent}{new},\n")
        return replace(text, before.start, before.start, f"{new}, ")

    # Append after the last item.
    last = items[-1]
    close = node.end - 1
    if last.comma is not None:  # trailing comma style
        if multiline:
            position = min(line_end(text, last.comma), close)
            return replace(text, position, position, f"\n{indent}{new},")
        return replace(text, last.comma + 1, last.comma + 1, f" {new},")
    if multiline:
        position = min(line_end(text, last.end), close)
        text = replace(text, position, position, f"\n{indent}{new}")
        return replace(text, last.end, last.end, ",")
    return replace(text, last.end, last.end, f", {new}")


# ---------------------------------------------------------------- diff


def _canonical(value):
    return json.dumps(value, sort_keys=True)


def changes(old, new, path=()):
    """List of edits that turn `old` into `new`, in the order to apply them."""
    path = list(path)
    if old == new and type(old) is type(new):
        return []
    if isinstance(old, dict) and isinstance(new, dict) and old:
        result = [("remove", path + [k]) for k in old if k not in new]
        for k, v in new.items():
            if k in old:
                result += changes(old[k], v, path + [k])
            else:
                result.append(("insert", path, None, k, v))
        return result
    if isinstance(old, list) and isinstance(new, list) and old:
        result = []
        matcher = SequenceMatcher(None, [_canonical(v) for v in old],
                                  [_canonical(v) for v in new], autojunk=False)
        # From the end, so the indices of the earlier items stay valid.
        for tag, i1, i2, j1, j2 in reversed(matcher.get_opcodes()):
            if tag == "equal":
                continue
            if tag == "replace" and i2 - i1 == j2 - j1:
                for offset in range(i2 - i1):
                    result += changes(old[i1 + offset], new[j1 + offset], path + [i1 + offset])
                continue
            result += [("remove", path + [i]) for i in reversed(range(i1, i2))]
            result += [("insert", path, i1 + (j - j1), None, new[j]) for j in range(j1, j2)]
        return result
    return [("set", path, new)]


def update(text, new_value):
    """Return `text` changed so that it contains `new_value`.
    Raises ParseError if the text cannot be read."""
    old_value = json5.loads(text) if text.strip() else None
    if old_value is None or not text.strip():
        return render(new_value, "", "    ") + "\n"
    parse(text)  # fail early on syntax we do not understand

    for change in changes(old_value, new_value):
        if change[0] == "set":
            text = set_value(text, change[1], change[2])
        elif change[0] == "remove":
            text = remove_item(text, change[1])
        else:
            _, path, index, key, value = change
            if index is None:  # object member: at the end
                index = len(find(parse(text), path).items)
            text = insert_item(text, path, index, key, value)
    return text
