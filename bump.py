#!/usr/bin/env python3
"""
Bump a pack's version - the only way VERSION is ever changed.

    python3 bump.py <pack> major|minor|patch "what changed"

Rewrites VERSION in <pack>/build.py, every <NAME>-<old version> mention in the READMEs,
appends the note to CHANGELOG.md and rebuilds the pack so the new zip exists at once.
Nothing is committed or pushed - that is publish-packs.py in the server repo.

Which part to bump:
  patch  the same pack, drawn or tuned a little better: an icon redrawn, an alpha
         changed, a texture tweaked. Nobody would notice a feature.
  minor  something new that was not there: new glyphs or code points, new models,
         a new texture, a new variant. Everything old still works the same.
  major  the pack changes shape: a pack format jump, files or names that move,
         behaviour a player would have to relearn.
"""

import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).parent
SEMVER = re.compile(r"(\d+)\.(\d+)\.(\d+)")


def read_version(build_py):
    return re.search(r'^VERSION = "(\d+\.\d+\.\d+)"', build_py.read_text(encoding="utf-8"), re.M).group(1)


def read_name(build_py):
    return re.search(r'^NAME = "([^"]+)"', build_py.read_text(encoding="utf-8"), re.M).group(1)


def bumped(version, part):
    major, minor, patch = (int(x) for x in version.split("."))
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def bump(pack, part, note):
    pack_dir = HERE / pack
    build_py = pack_dir / "build.py"
    if not build_py.exists():
        sys.exit(f"no pack called {pack!r}")
    if part not in ("major", "minor", "patch"):
        sys.exit("part must be major, minor or patch")
    name, old = read_name(build_py), read_version(build_py)
    new = bumped(old, part)

    text = build_py.read_text(encoding="utf-8")
    build_py.write_text(text.replace(f'VERSION = "{old}"', f'VERSION = "{new}"', 1), encoding="utf-8")
    for readme in (pack_dir / "README.md", HERE / "README.md"):
        if readme.exists():
            t = readme.read_text(encoding="utf-8")
            readme.write_text(t.replace(f"{name}-{old}", f"{name}-{new}"), encoding="utf-8")

    changelog = HERE / "CHANGELOG.md"
    entry = f"## {name} {new}\n\n{note.strip()}\n"
    if changelog.exists():
        head, sep, rest = changelog.read_text(encoding="utf-8").partition("\n## ")
        changelog.write_text(head.rstrip("\n") + "\n\n" + entry + (sep + rest if sep else ""), encoding="utf-8")
    else:
        changelog.write_text("# Changelog\n\nOne entry per published version, newest first.\n\n" + entry, encoding="utf-8")

    print(f"{name} {old} -> {new} ({part})")
    subprocess.run([sys.executable, str(HERE / "build.py"), pack], check=True)
    return new


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    bump(sys.argv[1], sys.argv[2], sys.argv[3])
