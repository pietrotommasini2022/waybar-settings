from gi.repository import Gtk

class ModulePage(Gtk.Box):

    def __init__(self, module_name, settings):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_top=12, margin_bottom=12, margin_start=12, margin_end=12)

        self.settings = settings
        self.append(Gtk.Label(label=module_name))

        if not settings:
            self.append(Gtk.Label(label="No settings acquired", xalign=0))
        else:
            for setting_name, setting_value in settings.items():
                box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                box.append(Gtk.Label(label=f"{setting_name}", xalign=0, hexpand=True))
                box.append(self.create_editor(setting_name, setting_value))
                self.append(box)

    
    def on_text_changed(self, entry, name):
        self.settings[name] = entry.get_text()
    
    def on_switch_changed(self, switch, pspec, name):
        self.settings[name] = switch.get_active()

    def on_spin_changed(self, spin, name):
        self.settings[name] = int(spin.get_value())

    def create_editor(self, name, value):
        match value:
            case str():
                entry = Gtk.Entry(text=value)
                entry.connect("changed", self.on_text_changed, name)
                return entry
            case bool():
                switch = Gtk.Switch(active=value)
                switch.connect("notify::active", self.on_switch_changed, name)
                return switch
            case int():
                spin = Gtk.SpinButton.new_with_range(0, 10000, 1)
                spin.set_value(value)
                spin.connect("value-changed", self.on_spin_changed, name)
                return spin
            case _:
                return Gtk.Label(label=f"{value}")


