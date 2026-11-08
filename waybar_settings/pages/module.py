from gi.repository import Gtk

class ModulePage(Gtk.Box):
    def __init__(self, module_name, settings):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        self.append(Gtk.Label(label=module_name))

        if not settings:
            self.append(Gtk.Label(label="No settings acquired", xalign=0))
        else:
            for setting_name, setting_value in settings.items():
                self.append(Gtk.Label(label=f"{setting_name}: {setting_value}", xalign=0))
