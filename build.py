#!/usr/bin/env python3
"""
Build every pack in this repo.

Each pack is a folder with a build.py that exposes NAME, VERSION and main(), where
main() builds the pack and returns the path of the zip that ships - which sits next
to the build script under the name <NAME>-<VERSION>[-variant].zip, because that path
is the URL the server hands to players. Run this after any change; the server repo's
publish-packs.py runs it again before publishing, so a forgotten build never ships.

    python3 build.py            build all, print name / version / file / sha1
    python3 build.py serverui   one pack
"""

import hashlib
import importlib.util
import pathlib
import sys

HERE = pathlib.Path(__file__).parent


def pack_dirs():
    return sorted(p.parent for p in HERE.glob("*/build.py"))


def load(pack_dir):
    spec = importlib.util.spec_from_file_location(f"pack_{pack_dir.name}", pack_dir / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build(pack_dir):
    module = load(pack_dir)
    print(f"{module.NAME} {module.VERSION}")
    zip_path = module.main()
    return {"dir": pack_dir.name, "name": module.NAME, "version": module.VERSION,
            "file": zip_path.name, "path": zip_path,
            "sha1": hashlib.sha1(zip_path.read_bytes()).hexdigest()}


def build_all(only=None):
    return [build(d) for d in pack_dirs() if only is None or d.name == only]


if __name__ == "__main__":
    only = sys.argv[1] if len(sys.argv) > 1 else None
    results = build_all(only)
    if not results:
        sys.exit(f"no pack called {only!r} - have: {', '.join(d.name for d in pack_dirs())}")
    print()
    for r in results:
        print(f"{r['name']:12} {r['version']:8} {r['file']:36} sha1 {r['sha1']}")
