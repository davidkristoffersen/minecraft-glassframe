#!/usr/bin/env python3
"""
Replay Minecraft's culling rule over the built models.

The rule: a quad carrying `cullface: D` is dropped when the block in direction D
occludes that side. An opaque block occludes; so does an identical glass block,
which is how vanilla merges glass against its own kind. Air, a different glass
colour and a pane do not.

Two things are checked. First, that the borderless build draws no seam
anywhere, in any orientation. Second - the reason the other builds exist - that
a border frame provably cannot: every strip that outlines one shape is a seam
inside another.
"""

import json
import sys

import build as gf

OFFSETS = {"north": (0, 0, -1), "south": (0, 0, 1), "west": (-1, 0, 0),
           "east": (1, 0, 0), "up": (0, 1, 0), "down": (0, -1, 0)}

failures = []


def check(label, ok, detail=""):
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}{'  ' + detail if detail else ''}")
    if not ok:
        failures.append(label)


def occludes(neighbour, me):
    if neighbour is None:
        return False
    if neighbour == "solid":
        return True
    return neighbour == me


def visible_quads(world, pos, model):
    me = world.get(pos)
    out = []
    for element in model["elements"]:
        for side, face in element["faces"].items():
            cull = face.get("cullface")
            if cull is None:
                out.append((side, tuple(element["from"]), tuple(element["to"]), None))
                continue
            dx, dy, dz = OFFSETS[cull]
            if not occludes(world.get((pos[0] + dx, pos[1] + dy, pos[2] + dz)), me):
                out.append((side, tuple(element["from"]), tuple(element["to"]), cull))
    return out


def glass_model():
    return json.loads((gf.SRC / "assets/minecraft/models/block/glass.json").read_text())


FLOOR = ({(x, 0, z): "glass" for x in range(3) for z in range(3)}, (1, 0, 1))
WALL_XY = ({(x, y, 0): "glass" for x in range(3) for y in range(3)}, (1, 1, 0))
WALL_ZY = ({(0, y, z): "glass" for y in range(3) for z in range(3)}, (0, 1, 1))


def main():
    print("the rim build (default) - clear glass, floors outlined")
    gf.build("rim")
    model = glass_model()
    quads = visible_quads(*FLOOR, model)
    check("a floor is clear between its blocks", len(quads) == 2,
          f"{len(quads)} quads")
    corner = visible_quads(FLOOR[0], (0, 0, 0), model)
    check("its corner block carries the rim, top and bottom",
          sorted(c for s, _, _, c in corner if s != c) == ["north", "north", "west", "west"])
    wall = visible_quads(*WALL_XY, model)
    strips = sorted(set(c for s, _, _, c in wall if s != c))
    check("a tall wall keeps level lines - the known cost",
          strips == ["north", "south"], f"culled by {strips}")
    check("but no upright lines at all in a wall",
          not any(s in ("north", "south", "east", "west") for s, _, _, c in wall if s != c))

    print("\nthe borderless build - zero seams anywhere")
    gf.build("borderless")
    model = glass_model()
    for name, (world, pos) in [("a 3x3 floor", FLOOR), ("a 3x3 wall", WALL_XY),
                               ("the same wall turned 90 degrees", WALL_ZY)]:
        quads = visible_quads(world, pos, model)
        seams = [q for q in quads if q[0] != q[3]]
        check(f"{name}: middle block draws no seam",
              len(seams) == 0 and len(quads) == 2,
              f"{len(quads)} quads, {len(seams)} seams")

    cube = {(x, y, z): "glass" for x in range(3) for y in range(3) for z in range(3)}
    check("a solid glass cube draws nothing inside itself",
          len(visible_quads(cube, (1, 1, 1), model)) == 0)
    check("a lone block still draws all six sides",
          len(visible_quads({(0, 0, 0): "glass"}, (0, 0, 0), model)) == 6)
    check("a side against stone is dropped, the rest stay",
          len(visible_quads({(0, 0, 0): "glass", (0, -1, 0): "solid"}, (0, 0, 0), model)) == 5)
    check("clear glass does not merge into red stained glass",
          len(visible_quads({(0, 0, 0): "glass", (-1, 0, 0): "red_stained_glass"},
                            (0, 0, 0), model)) == 6)

    panes = [n for n in (gf.SRC / "assets/minecraft/models/block").iterdir()
             if "pane" in n.name]
    check("the five pane templates are rebuilt too", len(panes) == 5,
          f"{sorted(p.stem.replace('template_glass_pane_', '') for p in panes)}")
    edge = any("#edge" in p.read_text() for p in panes)
    check("no #edge geometry left - that is the seam between two panes", not edge)

    print("\nwhy a frame on the rim cannot work (this is the proof, not a bug)")
    gf.build("frame")
    model = glass_model()
    seam_strips = set()
    for name, (world, pos) in [("floor", FLOOR), ("wall", WALL_XY), ("wall turned", WALL_ZY)]:
        for side, _, _, cull in visible_quads(world, pos, model):
            if side == cull:
                continue
            dx, dy, dz = OFFSETS[side]
            if world.get((pos[0] + dx, pos[1] + dy, pos[2] + dz)) == "glass":
                seam_strips.add((side, cull))
    every = {(f, c) for f in OFFSETS for c in OFFSETS
             if c != f and OFFSETS[c] != tuple(-v for v in OFFSETS[f])}
    check("every border strip is a seam in some orientation",
          seam_strips == every, f"{len(seam_strips)} of {len(every)}")
    check("no strip survives all three shapes", not (every - seam_strips),
          f"survivors: {sorted(every - seam_strips) or 'none'}")

    print("\ngeometry sanity (borderless)")
    gf.build("borderless")
    model = glass_model()
    check("every element is a flat quad",
          all(sum(1 for a, b in zip(e["from"], e["to"]) if a == b) == 1
              for e in model["elements"]))
    check("nothing pokes outside the block",
          all(all(0 <= v <= 16 for v in e["from"] + e["to"]) for e in model["elements"]))
    check("six sides, one quad each", len(model["elements"]) == 6)

    print()
    if failures:
        print(f"{len(failures)} FAILED: " + ", ".join(failures))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
