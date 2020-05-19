import collections
import importlib
import sys
import pytest
import runpy
from mypy.build import build
from mypy.modulefinder import BuildSource
from mypy.options import Options


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


def test_import_error():
    with pytest.raises(ImportError, match="gino-nonexist"):
        # noinspection PyUnresolvedReferences
        from gino.ext import nonexist


@pytest.fixture
def extensions(mocker):
    EntryPoint = collections.namedtuple("EntryPoint", ["name", "value"])
    importlib_metadata = mocker.Mock()
    importlib_metadata.entry_points = lambda: {
        "gino.extensions": [
            EntryPoint("demo1", "tests.stub1"),
            EntryPoint("demo2", "tests.stub2"),
        ]
    }
    mocker.patch.dict("sys.modules", {"importlib.metadata": importlib_metadata})


def test_list(mocker, extensions):
    mocker.patch("sys.argv", ["", "list"])
    stdout = mocker.patch("sys.stdout.write")
    runpy.run_module("gino.ext", run_name="__main__")
    out = "".join(args[0][0] for args in stdout.call_args_list)
    assert "tests.stub1" in out
    assert "tests.stub2" in out
    assert "gino.ext.demo1" in out
    assert "gino.ext.demo2" in out
    assert out.count("no stub file") == 2

    mocker.patch("sys.argv", [""])
    runpy.run_module("gino.ext", run_name="__main__")


def test_type_check(mocker, extensions):
    mocker.patch("sys.argv", ["", "clean"])
    runpy.run_module("gino.ext", run_name="__main__")

    result = build(
        [BuildSource(None, None, "from gino.ext.demo3 import s3")], Options()
    )
    assert result.errors

    result = build(
        [BuildSource(None, None, "from gino.ext.demo1 import s1")], Options()
    )
    assert result.errors

    mocker.patch("sys.argv", ["", "stub"])
    runpy.run_module("gino.ext", run_name="__main__")
    runpy.run_module("gino.ext", run_name="__main__")

    try:
        result = build(
            [BuildSource(None, None, "from gino.ext.demo1 import s1")], Options()
        )
        assert not result.errors

        result = build(
            [BuildSource(None, None, "from gino.ext.demo1 import s2")], Options()
        )
        assert result.errors

        result = build(
            [BuildSource(None, None, "from gino.ext.demo2 import s2")], Options()
        )
        assert not result.errors

        result = build(
            [BuildSource(None, None, "from gino.ext.demo2 import s1")], Options()
        )
        assert result.errors
    finally:
        mocker.patch("sys.argv", ["", "clean"])
        runpy.run_module("gino.ext", run_name="__main__")
