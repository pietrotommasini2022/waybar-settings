# Module schemas

One JSON file per Waybar module. They describe every option in plain English so
Waybar Settings can build friendly pages. Generated from the official Waybar manual
pages (`man/*.scd` in the Waybar repository) plus hand-written texts.

## File names

The module name with `/` replaced by `_`:

| Module in the config     | Schema file                 |
|--------------------------|-----------------------------|
| `clock`                  | `clock.json`                |
| `hyprland/workspaces`    | `hyprland_workspaces.json`  |
| `battery#bat2`           | `battery.json` (drop `#…`)  |
| `custom/menu`            | `custom.json` (all `custom/…` share it) |
| `group/hardware`         | `group.json` (all `group/…` share it)   |

`bar.json` describes the bar itself (position, height, margins…).

## Top level

| Field          | Meaning |
|----------------|---------|
| `module`       | Module name as used in the config |
| `title`        | Friendly name for the sidebar |
| `description`  | One sentence explaining what the module does |
| `manual`       | Man page with the full official documentation |
| `reviewed`     | `true` if all texts were rewritten for beginners; `false` means some descriptions are still the official (technical) text |
| `placeholders` | List of `{token, description}` usable in the module's formats |
| `patterns`     | Optional: template options like `format-<lang>` |
| `settings`     | The options (see below) |

## Each setting

| Field          | Meaning |
|----------------|---------|
| `label`        | Friendly name |
| `description`  | Plain-English explanation |
| `type`         | `string`, `integer`, `number`, `boolean`, `array`, `object` or `enum` |
| `options`      | For `enum`: list of `{value, label}` |
| `default`      | Waybar's value when the option is not set |
| `default_note` | Explanation of the default when it is not a simple value |
| `unit`         | `seconds`, `pixels`, `%`… |
| `min`, `max`, `step` | Limits for numbers |
| `group`        | Section of the page: `Display`, `Tooltip`, `Click & scroll`, `Menu`, `Layout`, `Behavior`… |
| `advanced`     | `true` for options most people never need |
| `presets`      | Ready-made values `{value, label}`, for example time formats |
| `also_accepts` | Other types the option accepts |
| `doc`          | The official text from the manual |
| `settings`     | For `object` options: the nested options, same format |
