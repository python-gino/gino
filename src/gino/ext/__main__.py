"""Generate typing stubs for extensions.

    $ python -m gino.ext

"""
import sys
import os

try:
    from importlib.metadata import entry_points
except ImportError:
    from importlib_metadata import entry_points


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cmd = sys.argv[1] if len(sys.argv) == 2 else ""
    eps = list(entry_points().get("gino.extensions", []))

    if cmd == "stub":
        added = False
        for ep in eps:
            path = os.path.join(base_dir, ep.name + ".pyi")
            if not os.path.exists(path):
                added = True
                print("Adding " + path)
                with open(path, "w") as f:
                    f.write("from " + ep.value + " import *")
        if not added:
            print("Stub files are up to date.")

    elif cmd == "clean":
        removed = False
        for filename in os.listdir(base_dir):
            if filename.endswith(".pyi"):
                removed = True
                path = os.path.join(base_dir, filename)
                print("Removing " + path)
                os.remove(path)
        if not removed:
            print("No stub files found.")

    elif cmd == "list":
        name_size = max(len(ep.name) for ep in eps)
        value_size = max(len(ep.value) for ep in eps)
        for ep in eps:
            path = os.path.join(base_dir, ep.name + ".pyi")
            if not os.path.exists(path):
                path = "no stub file"
            print(
                "%s -> gino.ext.%s (%s)"
                % (ep.value.ljust(value_size), ep.name.ljust(name_size), path)
            )

    else:
        print("Manages GINO extensions:")
        print()
        print("  python -m gino.ext COMMAND")
        print()
        print("Available commands:")
        print()
        print("  stub    Generate gino/ext/*.pyi stub files for type checking.")
        print("  clean   Remove the generated stub files.")
        print("  list    List installed GINO extensions.")
