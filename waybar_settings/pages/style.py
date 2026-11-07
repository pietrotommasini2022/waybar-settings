from gi.repository import Gtk

class StylePage(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.append(Gtk.Label(label="Qui ci andrà lo stile"))