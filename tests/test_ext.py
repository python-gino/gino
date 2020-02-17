import collections
import importlib
import sys


def installed():
    rv = 0
    for finder in sys.meta_path:
        if type(finder).__name__ == "_GinoExtensionCompatFinder":
            rv += 1
    return rv


def test_install():
    from gino import ext

    importlib.reload(ext)

    assert installed() == 1

    ext._GinoExtensionCompatFinder().install()
    assert installed() == 1

    ext._GinoExtensionCompatFinder.uninstall()
    assert not installed()

    ext._GinoExtensionCompatFinder().uninstall()
    assert not installed()

    ext._GinoExtensionCompatFinder().install()
    assert installed() == 1

    ext._GinoExtensionCompatFinder().install()
    assert installed() == 1


def test_import(mocker):
    from gino import ext

    importlib.reload(ext)

    EntryPoint = collections.namedtuple("EntryPoint", ["name", "value"])
    mocker.patch(
        "gino.ext.entry_points",
        new=lambda: {
            "gino.extensions": [
                EntryPoint("demo", "tests.stub1"),
                EntryPoint("demo2", "tests.stub2"),
            ]
        },
    )
    ext._GinoExtensionCompatFinder().install()
    from gino.ext import demo

    assert sys.modules["tests.stub1"] is sys.modules["gino.ext.demo"] is demo

    from tests import stub2
    from gino.ext import demo2

    assert sys.modules["tests.stub2"] is sys.modules["gino.ext.demo2"] is demo2 is stub2
