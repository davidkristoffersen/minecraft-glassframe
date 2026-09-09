#!/usr/bin/env python3
"""
Build GlassFrame: a connected-glass resource pack that needs no mods.

The problem it solves
---------------------
Vanilla decides whether to draw a face by asking "does the neighbour occlude
this side?". Stone and glass both answer yes, so a resource pack can never ask
"is my neighbour glass?" - which is why every good-looking connected-glass pack
on the internet requires OptiFine or Continuity, and does nothing without them.

What CAN be done is choose, per quad, WHICH neighbour the occlusion test looks
at: a model face may carry a `cullface` pointing in a different direction than
the face itself. That is the whole trick here.

Each glass block is drawn as, per side:

  * one centre quad, inset 1px, culled by its own direction - so two glass
    blocks facing each other still merge, exactly like vanilla.
  * four 1px border strips along the edges of that side, each culled by the
    neighbour it runs along. The strip on the west edge of the north face is
    culled by the block to the WEST, so a glass block beside this one removes
    the line and a wall reads as one sheet, while the outside edge of the wall
    keeps its frame.

The pack every other "vanilla connected glass" ships culls those border strips
by the direction they face instead, which is why a wall keeps a visible line at
every join - the neighbour beside you never removes a quad pointing forwards.

Known limit (unavoidable, one cullface per quad)
------------------------------------------------
A quad can test one neighbour, but a border strip really wants two conditions:
"my side is visible" AND "the wall does not continue this way". We keep the
second. So inside a glass volume 2+ blocks deep, the shared faces still draw
their border strips, visible as faint outlines through the glass. Single
thickness windows and walls - the reason anyone installs this - are exact.

Panes are deliberately untouched. A pane's blockstate says "connected" for a
neighbouring pane and for solid stone alike, so removing its frame removes it
against dirt too. Vanilla pane behaviour is the closest thing to correct.

No textures are shipped: the models sample the vanilla glass texture, the inner
16x16 area for the centre and the 1px border ring for the strips, so the pack
follows whatever other texture pack is loaded above it.
"""

import json
import pathlib
import shutil
import zipfile

PACK_FORMAT = 88          # 26.2, from the server jar's version.json
VERSION = "1.0.1"

HERE = pathlib.Path(__file__).parent
SRC = HERE / "src"
DIST = HERE / "dist"

COLOURS = ["white", "orange", "magenta", "light_blue", "yellow", "lime", "pink",
           "gray", "light_gray", "cyan", "purple", "blue", "brown", "green",
           "red", "black"]

# Per side: the axis it sits on, its outward direction, and the four lateral
# neighbours whose presence should erase the border strip on that edge.
#   plane      - (axis, coordinate) of the face
#   into       - +1/-1: which way is "into the block" along that axis
#   laterals   - lateral direction -> (axis, near_edge) the strip runs along
SIDES = {
    "north": {"axis": "z", "at": 0,  "into": +1},
    "south": {"axis": "z", "at": 16, "into": -1},
    "west":  {"axis": "x", "at": 0,  "into": +1},
    "east":  {"axis": "x", "at": 16, "into": -1},
    "up":    {"axis": "y", "at": 16, "into": -1},
    "down":  {"axis": "y", "at": 0,  "into": +1},
}

# The two in-plane axes for each side, and which direction sits at the low and
# high end of each. The first pair is drawn flush, the second pair 0.1px deeper,
# so the quads that meet at a corner never land on the same plane.
IN_PLANE = {
    "north": [("x", "west", "east"), ("y", "down", "up")],
    "south": [("x", "west", "east"), ("y", "down", "up")],
    "west":  [("z", "north", "south"), ("y", "down", "up")],
    "east":  [("z", "north", "south"), ("y", "down", "up")],
    "up":    [("x", "west", "east"), ("z", "north", "south")],
    "down":  [("x", "west", "east"), ("z", "north", "south")],
}

AXES = ["x", "y", "z"]
CORNER_OFFSET = 0.1       # px, keeps corner quads off each other's plane


def _point(axis_values):
    return [axis_values[a] for a in AXES]


def _element(side, spans, depth, uv, cullface):
    """One flat quad on `side`, spanning `spans` in the two in-plane axes."""
    cfg = SIDES[side]
    coord = cfg["at"] + cfg["into"] * depth
    low = dict(spans)
    high = dict(spans)
    for axis in spans:
        low[axis], high[axis] = spans[axis]
    low[cfg["axis"]] = high[cfg["axis"]] = coord
    return {
        "from": _point(low),
        "to": _point(high),
        "faces": {side: {"uv": uv, "texture": "#glass", "cullface": cullface}},
    }


def side_elements(side):
    """Centre quad plus the four border strips for one side of the cube."""
    (a1, a1_low, a1_high), (a2, a2_low, a2_high) = IN_PLANE[side]
    out = [
        # the clear middle: merges with the neighbour on this side, like vanilla
        _element(side, {a1: (1, 15), a2: (1, 15)}, 0, [1, 1, 15, 15], side),
        # strips along a1: erased by the neighbour they run towards
        _element(side, {a1: (0, 1), a2: (0, 16)}, 0, [0, 0, 1, 16], a1_low),
        _element(side, {a1: (15, 16), a2: (0, 16)}, 0, [15, 0, 16, 16], a1_high),
        # strips along a2, set a hair deeper so the corners do not z-fight
        _element(side, {a1: (0, 16), a2: (0, 1)}, CORNER_OFFSET, [0, 15, 16, 16], a2_low),
        _element(side, {a1: (0, 16), a2: (15, 16)}, CORNER_OFFSET, [0, 0, 16, 1], a2_high),
    ]
    return out


def block_model(texture):
    elements = []
    for side in SIDES:
        elements.extend(side_elements(side))
    return {
        # block/block only for the inventory display transforms; the cube itself
        # is ours. Vanilla reaches it through cube_all -> cube -> block.
        "parent": "minecraft:block/block",
        "textures": {
            "particle": texture,
            # vanilla glass and stained glass both carry force_translucent in
            # 26.2 (block/glass.json); without it the block lands in the wrong
            # render pass and sorts against water and other glass incorrectly
            "glass": {"force_translucent": True, "sprite": texture},
        },
        "elements": elements,
    }


def build():
    if SRC.exists():
        shutil.rmtree(SRC)
    models = SRC / "assets" / "minecraft" / "models" / "block"
    models.mkdir(parents=True)

    # 26.x reads min_format/max_format. The older supported_formats array is not
    # enough on its own - a pack carrying only pack_format + supported_formats
    # shows up as "incompatible or broken" in the selection screen even when the
    # number is right. Every pack that loads on 26.2 declares min/max, and some
    # carry no pack_format at all, so these two are what the client goes by.
    (SRC / "pack.mcmeta").write_text(json.dumps({
        "pack": {
            "description": "GlassFrame " + VERSION
                           + "§7 - frame outside, seamless inside. No mods.",
            "pack_format": PACK_FORMAT,
            "min_format": PACK_FORMAT,
            "max_format": 2147483647,
        }
    }, indent=2) + "\n")

    names = {"glass": "minecraft:block/glass"}
    for colour in COLOURS:
        names[f"{colour}_stained_glass"] = f"minecraft:block/{colour}_stained_glass"
    for name, texture in names.items():
        (models / f"{name}.json").write_text(
            json.dumps(block_model(texture), indent=1) + "\n")

    DIST.mkdir(exist_ok=True)
    out = DIST / f"GlassFrame-{VERSION}.zip"
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(SRC.rglob("*")):
            if path.is_file():
                z.write(path, path.relative_to(SRC).as_posix())
    return out, len(names)


if __name__ == "__main__":
    path, count = build()
    print(f"{path}  ({count} block models, {path.stat().st_size} bytes)")
