import sys
from importlib.abc import MetaPathFinder
from importlib.util import find_spec

from importlib_metadata import entry_points


class PluginFinder(MetaPathFinder):
    def __init__(self):
        self.entry_points = {
            __name__ + "." + ep.name: ep.value
            for ep in entry_points()["gino.extensions"]
        }

    def find_spec(self, fullname, path, target=None):
        if fullname in self.entry_points:
            spec = find_spec(self.entry_points[fullname])
            return spec


sys.meta_path.append(PluginFinder())
