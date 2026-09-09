#!/usr/bin/env python3
"""
Check the rule the GlassRim plugin draws by, on the shapes that broke every
resource-pack attempt. This mirrors Rims.barsFor in
servermenus/src/main/java/dev/david/glassrim/Rims.java - keep the two in step.

The rule, for the edge where faces A and B meet:

    A is visible and B is not the same glass   ->  the sheet stops here
    B is visible and A is not the same glass   ->  the sheet stops here

A face is visible when the neighbour is neither the same glass (vanilla merges
glass with its own kind) nor a full opaque block.

The point of the plugin is that this reads TWO neighbours at once, which is
exactly what a resource pack cannot do.
"""

import sys

DIRS = {"up": (0, 1, 0), "down": (0, -1, 0), "north": (0, 0, -1),
        "south": (0, 0, 1), "east": (1, 0, 0), "west": (-1, 0, 0)}
EDGES = [("up", "north"), ("up", "south"), ("up", "east"), ("up", "west"),
         ("down", "north"), ("down", "south"), ("down", "east"), ("down", "west"),
         ("north", "east"), ("north", "west"), ("south", "east"), ("south", "west")]

failures = []


def check(label, ok, detail=""):
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}{'  ' + detail if detail else ''}")
    if not ok:
        failures.append(label)


def at(world, pos, d):
    dx, dy, dz = DIRS[d]
    return world.get((pos[0] + dx, pos[1] + dy, pos[2] + dz))


def bars(world, pos):
    """The edges of this block that carry a bar."""
    glass = world.get(pos)
    visible = {d: at(world, pos, d) != glass and at(world, pos, d) != "solid" for d in DIRS}
    same = {d: at(world, pos, d) == glass for d in DIRS}
    return [e for e in EDGES
            if (visible[e[0]] and not same[e[1]]) or (visible[e[1]] and not same[e[0]])]


def main():
    print("a flat glass floor")
    floor = {(x, 0, z): "glass" for x in range(3) for z in range(3)}
    check("nothing inside the sheet", bars(floor, (1, 0, 1)) == [])
    edge = bars(floor, (1, 0, 0))
    check("its north edge is outlined top and bottom",
          sorted(edge) == [("down", "north"), ("up", "north")], f"{sorted(edge)}")

    print("\nstacked slabs - the case a resource pack cannot do")
    stack = {(x, y, z): "glass" for x in range(3) for y in range(3) for z in range(3)}
    top = [e for e in bars(stack, (0, 2, 0)) if "up" in e]
    mid = [e for e in bars(stack, (0, 1, 0)) if "up" in e]
    bot = [e for e in bars(stack, (0, 0, 0)) if "up" in e]
    check("the top layer is outlined", sorted(top) == [("up", "north"), ("up", "west")],
          f"{sorted(top)}")
    check("the middle layer draws no top rim", mid == [], f"{mid}")
    check("the bottom layer draws no top rim", bot == [], f"{bot}")
    check("the stack keeps its upright corner",
          ("north", "west") in bars(stack, (0, 1, 0)))

    print("\nglass meeting things that are not glass")
    world = {(0, 0, 0): "glass", (0, 0, -1): "solid"}
    check("outlined against dirt - what the pack could never do",
          ("up", "north") in bars(world, (0, 0, 0)))
    world = {(0, 0, 0): "glass", (0, 0, -1): "red_stained_glass"}
    check("outlined against a different colour of glass",
          ("up", "north") in bars(world, (0, 0, 0)))
    world = {(0, 0, 0): "glass", (0, 0, -1): "glass"}
    check("not outlined against its own kind",
          ("up", "north") not in bars(world, (0, 0, 0)))

    print("\ntwo slabs pushed together become one sheet")
    apart = {(x, 0, z): "glass" for x in range(2) for z in range(2)}
    joined = dict(apart)
    joined.update({(x, 0, z): "glass" for x in range(2) for z in range(2, 4)})
    check("the seam is outlined while they are apart",
          ("up", "south") in bars(apart, (0, 0, 1)))
    check("and gone once they touch",
          ("up", "south") not in bars(joined, (0, 0, 1)))

    print("\na single glass block in the open")
    check("all twelve edges", len(bars({(0, 0, 0): "glass"}, (0, 0, 0))) == 12)

    print("\na glass wall, one block thick")
    wall = {(x, y, 0): "glass" for x in range(3) for y in range(3)}
    check("nothing inside the wall", bars(wall, (1, 1, 0)) == [])
    check("its top row is outlined",
          sorted(e for e in bars(wall, (1, 2, 0)) if "up" in e)
          == [("up", "north"), ("up", "south")])

    print()
    if failures:
        print(f"{len(failures)} FAILED: " + ", ".join(failures))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
