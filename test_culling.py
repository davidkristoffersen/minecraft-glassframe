#!/usr/bin/env python3
"""
Check the built models against Minecraft's culling rule, for layouts that
matter: a flat wall, a lone block, glass meeting stone, a stacked column.

The rule the client applies: a quad carrying `cullface: D` is dropped when the
block in direction D occludes that side. An opaque block occludes; so does an
identical glass block (vanilla merges glass against its own kind). Everything
else - air, a different glass colour, a pane - does not.

The wall test is the one that matters: with the border strips culled by the
neighbour they run towards, the inside of a wall must come out completely bare
and the frame must survive exactly on the outer rim.
"""

import json
import pathlib
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
    """Does `neighbour` hide the side of `me` that faces it?"""
    if neighbour is None:            # air
        return False
    if neighbour == "solid":         # stone, dirt, anything full and opaque
        return True
    return neighbour == me           # glass merges only with its own kind


def visible_quads(world, pos, model):
    """The quads of the block at `pos` that the client actually draws."""
    me = world.get(pos)
    out = []
    for element in model["elements"]:
        for side, face in element["faces"].items():
            cull = face["cullface"]
            dx, dy, dz = OFFSETS[cull]
            neighbour = world.get((pos[0] + dx, pos[1] + dy, pos[2] + dz))
            if not occludes(neighbour, me):
                out.append((side, tuple(element["from"]), tuple(element["to"]), cull))
    return out


def sides_of(quads, side):
    return [q for q in quads if q[0] == side]


def main():
    gf.build()
    model = json.loads((gf.SRC / "assets/minecraft/models/block/glass.json").read_text())
    print(f"model: {len(model['elements'])} quads, "
          f"{sum(len(e['faces']) for e in model['elements'])} faces\n")

    print("a lone glass block in the open")
    world = {(0, 0, 0): "glass"}
    q = visible_quads(world, (0, 0, 0), model)
    check("every side keeps its full frame", len(q) == 30, f"{len(q)} quads, want 30")
    check("north side = centre + 4 border strips", len(sides_of(q, "north")) == 5)

    print("\na flat 3x3 wall, single thickness, open air around it")
    world = {(x, y, 0): "glass" for x in range(3) for y in range(3)}
    middle = visible_quads(world, (1, 1, 0), model)
    north_mid = sides_of(middle, "north")
    check("middle block's face is bare - no seams", len(north_mid) == 1,
          f"{len(north_mid)} quads on its north side, want just the centre")
    check("the one quad left is the clear centre",
          north_mid and north_mid[0][3] == "north")

    corner = visible_quads(world, (0, 0, 0), model)
    north_corner = sides_of(corner, "north")
    culls = sorted(x[3] for x in north_corner)
    check("bottom-left block keeps its two outer edges",
          culls == ["down", "north", "west"], f"got {culls}")

    edge = visible_quads(world, (1, 0, 0), model)
    culls = sorted(x[3] for x in sides_of(edge, "north"))
    check("bottom-middle block keeps only its bottom edge",
          culls == ["down", "north"], f"got {culls}")

    total_border = 0
    for x in range(3):
        for y in range(3):
            qs = visible_quads(world, (x, y, 0), model)
            total_border += len([b for b in sides_of(qs, "north") if b[3] != "north"])
    check("wall front draws one unbroken rim, nothing inside", total_border == 12,
          f"{total_border} border strips, want 12 (4 corners x2 + 4 edges x1)")

    print("\nglass against stone")
    world = {(0, 0, 0): "glass", (0, 0, -1): "solid"}
    q = visible_quads(world, (0, 0, 0), model)
    check("the hidden side draws nothing the player can reach",
          not any(s == "north" and c == "north" for s, _, _, c in q),
          "centre is culled by the stone")
    world = {(0, 0, 0): "glass", (-1, 0, 0): "solid"}
    q = sides_of(visible_quads(world, (0, 0, 0), model), "north")
    check("glass running into stone drops the line at that seam, keeps the rest",
          sorted(x[3] for x in q) == ["down", "east", "north", "up"],
          f"got {sorted(x[3] for x in q)}")

    print("\na column of glass, stacked")
    world = {(0, 0, 0): "glass", (0, 1, 0): "glass"}
    lower = visible_quads(world, (0, 0, 0), model)
    check("no centre quad between the two blocks",
          not any(c == "up" for _, _, _, c in lower))
    north = sorted(x[3] for x in sides_of(lower, "north"))
    check("the column's front keeps its sides, loses the join",
          north == ["down", "east", "north", "west"], f"got {north}")

    print("\nstained glass of a different colour is not the same block")
    world = {(0, 0, 0): "glass", (-1, 0, 0): "red_stained_glass"}
    q = sides_of(visible_quads(world, (0, 0, 0), model), "north")
    check("clear glass keeps its edge against red glass",
          any(x[3] == "west" for x in q))

    print("\ngeometry sanity")
    flat = all(sum(1 for a, b in zip(e["from"], e["to"]) if a == b) == 1
               for e in model["elements"])
    check("every element is a flat quad", flat)
    inside = all(all(0 <= v <= 16 for v in e["from"] + e["to"])
                 for e in model["elements"])
    check("nothing pokes outside the block", inside)
    planes = {}
    for e in model["elements"]:
        for side in e["faces"]:
            axis = [i for i, (a, b) in enumerate(zip(e["from"], e["to"])) if a == b][0]
            key = (side, e["from"][axis])
            planes.setdefault(key, []).append((e["from"], e["to"]))
    overlaps = 0
    for (side, _), boxes in planes.items():
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i], boxes[j]
                if all(min(a[1][k], b[1][k]) - max(a[0][k], b[0][k]) > 0 for k in range(3)
                       if a[0][k] != a[1][k] or b[0][k] != b[1][k]):
                    overlaps += 1
    check("no two quads share a plane and overlap (no z-fighting)", overlaps == 0,
          f"{overlaps} overlapping pairs")

    print()
    if failures:
        print(f"{len(failures)} FAILED: " + ", ".join(failures))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
