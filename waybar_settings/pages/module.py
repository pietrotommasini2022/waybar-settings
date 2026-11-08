from gi.repository import Gtk

class ModulePage(Gtk.Box):
    def __init__(self, name):
        super().__init__()

        self.set_homogeneous(True)
        self.append(Gtk.Label(label=name))
