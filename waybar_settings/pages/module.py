from gi.repository import Gtk

class ModulePage(Gtk.Box):
    def __init__(self, module_name, settings):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        self.append(Gtk.Label(label=module_name))
