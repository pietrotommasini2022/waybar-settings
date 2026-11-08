from gi.repository import Gtk

class ModulePage(Gtk.Box):

    def __init__(self, module_name, settings):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_top=12, margin_bottom=12, margin_start=12, margin_end=12)

        self.append(Gtk.Label(label=module_name))

        if not settings:
            self.append(Gtk.Label(label="No settings acquired", xalign=0))
        else:
            for setting_name, setting_value in settings.items():
                box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                box.append(Gtk.Label(label=f"{setting_name}", xalign=0, hexpand=True))
                box.append(self.create_editor(setting_value))
                self.append(box)

    def create_editor(self, value):
        match value:
            case str():
                return Gtk.Entry(text=f"{value}")
            case bool():
                return Gtk.Switch(active=value)
            case int():
                spin = Gtk.SpinButton.new_with_range(0, 10000, 1)
                spin.set_value(value)
                return spin
            case _:
                return Gtk.Label(label=f"{value}")


