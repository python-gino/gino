"""
Namespace package for GINO extensions.

This namespace package didn't use any of the `3 official solutions
<https://packaging.python.org/guides/packaging-namespace-packages/>`__. Instead,
``gino.ext`` adds a hook into :data:`sys.meta_path`, and utilize the :ref:`entry-points`
to find the extensions.

Any GINO extension package should provide an entry point like this::

    [gino.extensions]
    starlette = gino_starlette

So that the Python package ``gino_starlette`` will also be importable through
``gino.ext.starlette``.
"""

import sys
from importlib.abc import MetaPathFinder, Loader
from importlib.machinery import ModuleSpec
from importlib.util import find_spec

try:
    from importlib.metadata import entry_points
except ImportError:
    from importlib_metadata import entry_points


class _GinoExtensionCompatProxyLoader(Loader):
    def __init__(self, fullname, loader):
        self._fullname = fullname
        self._loader = loader

    def create_module(self, spec):
        return self._loader.create_module(spec)

    def exec_module(self, mod):
        sys.modules[self._fullname] = mod
        return self._loader.exec_module(mod)


class _GinoExtensionCompatNoopLoader(Loader):
    def __init__(self, mod):
        self._mod = mod

    def create_module(self, spec):
        return self._mod

    def exec_module(self, mod):
        pass


class _GinoExtensionCompatFinder(MetaPathFinder):
    def __init__(self):
        self._redirects = {
            __name__ + "." + ep.name: ep.value
            for ep in entry_points().get("gino.extensions", [])
        }

    # noinspection PyUnusedLocal
    def find_spec(self, fullname, path, target=None):
        target = self._redirects.get(fullname)
        if target:
            mod = sys.modules.get(target)
            if mod is None:
                spec = find_spec(target)
                spec.loader = _GinoExtensionCompatProxyLoader(fullname, spec.loader)
                return spec
            else:
                return ModuleSpec(fullname, _GinoExtensionCompatNoopLoader(mod))
        elif fullname.startswith(__name__):
            raise ImportError(
                "Cannot import {} - is gino-{} a valid extension and installed?".format(
                    fullname, fullname[len(__name__) + 1 :]
                )
            )

    @classmethod
    def uninstall(cls):
        if sys.meta_path:
            for i in range(len(sys.meta_path) - 1, -1, -1):
                if type(sys.meta_path[i]).__name__ == cls.__name__:
                    del sys.meta_path[i]

    def install(self):
        self.uninstall()
        sys.meta_path.append(self)


_GinoExtensionCompatFinder().install()
