import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from .window import MainWindow

class WaybarSettingsApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.pietrotommasini.WaybarSettings")
    
    def do_activate(self):
        window = MainWindow(self)
        window.present()