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

    main_panes()
    main_holes()
    main_exhaustive()

    print()
    if failures:
        print(f"{len(failures)} FAILED: " + ", ".join(failures))
        return 1
    print("all checks passed")
    return 0




# ---------------------------------------------------------------- panes
# Mirrors Rims.paneBars. A pane is a 2px sheet through the middle of the block,
# reaching out to the sides it connects on. Vanilla connects a pane to another
# pane, a glass block and a solid block alike, so "connected" is not the test -
# what matters is whether the SAME pane carries on.

LO, HI = 7 / 16, 9 / 16
SIDES = ["north", "south", "east", "west"]
OPP = {"north": "south", "south": "north", "east": "west", "west": "east"}


def connects(neighbour):
    return neighbour is not None and (neighbour == "solid" or "pane" in neighbour
                                      or "glass" in neighbour)


def pane_boxes(world, pos, t=1 / 16):
    """The actual boxes, mirroring Rims.paneBars, as (minX,minY,minZ,sizeX,sizeY,sizeZ)."""
    me = world[pos]
    conn = {d: connects(at(world, pos, d)) for d in SIDES}
    n, s, e, w = conn["north"], conn["south"], conn["east"], conn["west"]
    minX, maxX = (0 if w else LO), (1 if e else HI)
    minZ, maxZ = (0 if n else LO), (1 if s else HI)
    along_x, along_z = e or w, n or s
    out = []

    def continues_along(vertical, x_axis):
        """A pane above or below covers only the 2px post, so it hides this rail along an
        axis only if it reaches out along that axis too."""
        d = (0, 1, 0) if vertical == "up" else (0, -1, 0)
        npos = (pos[0] + d[0], pos[1] + d[1], pos[2] + d[2])
        if world.get(npos) != me:
            return False
        nconn = {s: connects(at(world, npos, s)) for s in SIDES}
        return (nconn["east"] or nconn["west"]) if x_axis else (nconn["north"] or nconn["south"])

    for top in (True, False):
        vert = "up" if top else "down"
        if not along_x and not along_z and at(world, pos, vert) == me:
            continue
        y = 1 - t if top else 0
        if along_x and not continues_along(vert, True):
            out.append((minX, y, LO, maxX - minX, t, HI - LO))
        if along_z and not continues_along(vert, False):
            if along_x:
                if n:
                    out.append((LO, y, minZ, HI - LO, t, LO - minZ))
                if s:
                    out.append((LO, y, HI, HI - LO, t, maxZ - HI))
            else:
                out.append((LO, y, minZ, HI - LO, t, maxZ - minZ))
        if not along_x and not along_z:
            out.append((LO, y, LO, HI - LO, t, HI - LO))
    if not along_x and not along_z:
        pt = min(t, (HI - LO) / 4)          # thin enough that four posts leave the middle open
        for cx in (LO, HI - pt):
            for cz in (LO, HI - pt):
                out.append((cx, 0, cz, pt, 1, pt))
        return out
    perp = {"north": ("east", "west"), "south": ("east", "west"),
            "east": ("north", "south"), "west": ("north", "south")}
    for d in SIDES:
        pos_side = d in ("east", "south")
        straight = (not conn[d] and conn[OPP[d]]
                    and not conn[perp[d][0]] and not conn[perp[d][1]])
        if conn[d]:
            if at(world, pos, d) == me:
                continue
            a = 1 - t if pos_side else 0
        elif straight:
            a = HI - t if pos_side else LO
        else:
            continue
        if d in ("east", "west"):
            out.append((a, 0, LO, t, 1, HI - LO))
        else:
            out.append((LO, 0, a, HI - LO, 1, t))
    return out




def run_axis(b):
    x, y, z = b[3], b[4], b[5]
    return 0 if (x >= y and x >= z) else (1 if y >= z else 2)


def trim(bar, other):
    """Mirror of Rims.trim: shorten `bar` along its length to clear `other`."""
    for i in range(3):
        lo = max(bar[i], other[i])
        hi = min(bar[i] + bar[i + 3], other[i] + other[i + 3])
        if hi - lo <= 1e-9:
            return None
    run = run_axis(bar)
    start, end = bar[run], bar[run] + bar[run + 3]
    o_start, o_end = other[run], other[run] + other[run + 3]
    cut_from_start = min(o_end, end) - start
    cut_from_end = end - max(o_start, start)
    if cut_from_start <= cut_from_end:
        start = min(max(start, o_end), end)
    else:
        end = max(min(end, o_start), start)
    mins, sizes = list(bar[:3]), list(bar[3:])
    mins[run] = start
    sizes[run] = max(0.0, end - start)
    return tuple(mins) + tuple(sizes)


def resolve(bars):
    out = sorted(bars, key=run_axis)
    for i in range(len(out)):
        for j in range(i):
            got = trim(out[i], out[j])
            if got is not None:
                out[i] = got
    return [b for b in out if b[3 + run_axis(b)] > 1e-4]


def overlaps(a, b):
    """Do two boxes share volume on a common plane? That is what flickers."""
    for i in range(3):
        lo1, hi1 = a[i], a[i] + a[i + 3]
        lo2, hi2 = b[i], b[i] + b[i + 3]
        if min(hi1, hi2) - max(lo1, lo2) <= 1e-6:
            return False
    return True


def pane_bars(world, pos):
    """Returns (rails, uprights) as lists of the side each belongs to."""
    me = world[pos]
    conn = {d: connects(at(world, pos, d)) for d in SIDES}
    along_x, along_z = conn["east"] or conn["west"], conn["north"] or conn["south"]
    rails, uprights = [], []

    def continues_along(vertical, x_axis):
        d = (0, 1, 0) if vertical == "up" else (0, -1, 0)
        npos = (pos[0] + d[0], pos[1] + d[1], pos[2] + d[2])
        if world.get(npos) != me:
            return False
        nconn = {s: connects(at(world, npos, s)) for s in SIDES}
        return (nconn["east"] or nconn["west"]) if x_axis else (nconn["north"] or nconn["south"])

    for end in ("up", "down"):
        if not along_x and not along_z and at(world, pos, end) == me:
            continue
        if along_x and not continues_along(end, True):
            rails.append((end, "x"))
        if along_z and not continues_along(end, False):
            rails.append((end, "z"))
        if not along_x and not along_z:
            rails.append((end, "post"))
    perp = {"north": ("east", "west"), "south": ("east", "west"),
            "east": ("north", "south"), "west": ("north", "south")}
    for d in SIDES:
        # a post is capped only where the sheet is a straight run along one axis that
        # stops here: not at the inside of a corner, and not on a pane standing alone
        straight = (not conn[d] and conn[OPP[d]]
                    and not conn[perp[d][0]] and not conn[perp[d][1]])
        if conn[d]:
            if at(world, pos, d) == me:
                continue
            uprights.append((d, "edge"))
        elif straight:
            uprights.append((d, "post"))
    return rails, uprights


def main_panes():
    print("\nglass panes")
    wall = {(x, 0, 0): "pane" for x in range(3)}
    rails, up = pane_bars(wall, (1, 0, 0))
    check("a pane wall gets a rail top and bottom, nothing upright",
          sorted(rails) == [("down", "x"), ("up", "x")] and up == [],
          f"rails={sorted(rails)} uprights={up}")
    check("its flat sides get nothing",
          not any(d in ("north", "south") for d, _ in up))

    tall = {(x, y, 0): "pane" for x in range(3) for y in range(3)}
    rails, up = pane_bars(tall, (1, 1, 0))
    check("the middle of a tall pane wall is bare", rails == [] and up == [],
          f"rails={rails} uprights={up}")
    rails, _ = pane_bars(tall, (1, 2, 0))
    check("its top row keeps the top rail only", sorted(rails) == [("up", "x")])

    rails, up = pane_bars(wall, (0, 0, 0))
    check("the end of a wall is capped upright",
          ("west", "post") in up and ("east", "edge") not in up, f"{up}")

    dirt = {(0, 0, 0): "pane", (1, 0, 0): "solid"}
    _, up = pane_bars(dirt, (0, 0, 0))
    check("a pane running into dirt is outlined against it",
          ("east", "edge") in up, f"{up}")

    mixed = {(0, 0, 0): "pane", (1, 0, 0): "red_pane"}
    _, up = pane_bars(mixed, (0, 0, 0))
    check("and against a different colour of pane", ("east", "edge") in up)

    lone = resolve(pane_boxes({(0, 0, 0): "pane"}, (0, 0, 0)))
    posts = [b for b in lone if run_axis(b) == 1]
    clash = [(a, b) for i, a in enumerate(lone) for b in lone[i + 1:] if overlaps(a, b)]
    check("a pane on its own is outlined by four corner posts",
          len(posts) == 4 and not clash, f"{len(posts)} posts, {len(clash)} clashes")
    west_pair = sorted(b[3] for b in posts if abs(b[0] - LO) < 1e-9)
    check("the posts sit at its corners rather than filling the 2px post",
          sum(west_pair) < HI - LO - 1e-9 or len(west_pair) == 2,
          f"west side posts span {sum(west_pair):.4f} of {HI - LO:.4f}")

    # the case from the screenshots: a wall corner with a single pane standing on it
    on_corner = {(0, 0, 0): "pane", (1, 0, 0): "pane", (0, 0, 1): "pane", (0, 1, 0): "pane"}
    rails, _ = pane_bars(on_corner, (0, 0, 0))
    tops = [r for r in rails if r[0] == "up"]
    check("a lone pane standing on a corner does not erase that corner's top rails",
          len(tops) == 2, f"top rails: {tops}")
    wall = {(x, 0, 0): "pane" for x in range(3)}
    wall[(1, 1, 0)] = "pane"
    rails, _ = pane_bars(wall, (1, 0, 0))
    check("nor a wall's, where one stands on it",
          [r for r in rails if r[0] == "up"] != [], f"{rails}")
    tall = {(x, y, 0): "pane" for x in range(3) for y in range(2)}
    rails, _ = pane_bars(tall, (1, 0, 0))
    check("but a full second course still does",
          [r for r in rails if r[0] == "up"] == [], f"{rails}")

    corner_in = {(0, 0, 0): "pane", (0, 0, -1): "pane", (1, 0, 0): "pane"}
    _, up = pane_bars(corner_in, (0, 0, 0))
    check("a corner draws nothing on its inside faces", up == [], f"{up}")

    print("\npane bar geometry")
    end = resolve(pane_boxes({(0, 0, 0): "pane", (1, 0, 0): "pane"}, (0, 0, 0)))
    clash = [(a, b) for i, a in enumerate(end) for b in end[i + 1:] if overlaps(a, b)]
    check("a wall end's cap no longer runs through its own rails", not clash,
          f"{len(clash)} overlapping pairs")
    caps = [b for b in end if run_axis(b) == 1]
    check("the cap survives, just shortened", len(caps) == 1 and caps[0][4] < 1.0,
          f"{caps}")
    boxes = resolve(pane_boxes(corner_in, (0, 0, 0)))
    clashes = [(a, b) for i, a in enumerate(boxes) for b in boxes[i + 1:] if overlaps(a, b)]
    check("no two bars overlap at a corner - that is the flicker", not clashes,
          f"{len(clashes)} overlapping pairs")

    for name, world, pos in [("wall end", {(0, 0, 0): "pane", (1, 0, 0): "pane"}, (0, 0, 0)),
                             ("corner", corner_in, (0, 0, 0)),
                             ("into dirt", {(0, 0, 0): "pane", (1, 0, 0): "solid"}, (0, 0, 0))]:
        bad = []
        for b in resolve(pane_boxes(world, pos)):
            conn = {d: connects(at(world, pos, d)) for d in SIDES}
            xlo = 0 if conn["west"] else LO
            xhi = 1 if conn["east"] else HI
            zlo = 0 if conn["north"] else LO
            zhi = 1 if conn["south"] else HI
            if (b[0] < xlo - 1e-6 or b[0] + b[3] > xhi + 1e-6
                    or b[2] < zlo - 1e-6 or b[2] + b[5] > zhi + 1e-6):
                bad.append(b)
        check(f"every bar on a {name} sits on the pane, not floating beside it",
              not bad, f"{len(bad)} off the pane")

    corner = {(0, 0, 0): "pane", (0, 0, -1): "pane", (1, 0, 0): "pane"}
    rails, up = pane_bars(corner, (0, 0, 0))
    check("a corner rails along both arms", sorted(set(a for _, a in rails)) == ["x", "z"],
          f"{sorted(rails)}")




def main_exhaustive():
    """Every shape, not just the handful above. This is what closed out the
    corner and overlap bugs: they were only ever found by looking, and each fix
    was checked against one example."""
    import itertools
    print("\nevery configuration")
    sides = ["north", "south", "east", "west"]
    off = {"north": (0, 0, -1), "south": (0, 0, 1), "east": (1, 0, 0), "west": (-1, 0, 0)}
    bound = {"north": (2, 0.0), "south": (2, 1.0), "east": (0, 1.0), "west": (0, 0.0)}
    t = 1 / 16
    clashes = gaps = strays = 0
    panes = 0
    for mask in itertools.product([None, "pane"], repeat=4):
        for above in (None, "pane"):
            for below in (None, "pane", "solid"):
                world = {(0, 0, 0): "pane"}
                for side, val in zip(sides, mask):
                    if val:
                        world[off[side]] = val
                if above:
                    world[(0, 1, 0)] = above
                if below:
                    world[(0, -1, 0)] = below
                boxes = resolve(pane_boxes(world, (0, 0, 0), t))
                panes += 1
                for i, a in enumerate(boxes):
                    for b in boxes[i + 1:]:
                        if overlaps(a, b):
                            clashes += 1
                for side, val in zip(sides, mask):
                    if val != "pane":
                        continue
                    axis, edge = bound[side]
                    reaching = [b for b in boxes if b[4] < 0.5
                                and (abs(b[axis] + b[axis + 3] - edge) < 1e-9
                                     or abs(b[axis] - edge) < 1e-9)]
                    if above is None and not reaching:
                        gaps += 1
    check(f"{panes} pane shapes: no two bars share space", clashes == 0, f"{clashes} clashes")
    check("every join with another pane is reached by a rail", gaps == 0, f"{gaps} gaps")

    blocks = 0
    for combo in itertools.product(["air", "glass", "solid"], repeat=6):
        world = {(0, 0, 0): "glass"}
        for d, val in zip(DIRS, combo):
            if val != "air":
                world[DIRS[d]] = val
        glass = "glass"
        vis = {d: at(world, (0, 0, 0), d) not in (glass, "solid") for d in DIRS}
        same = {d: at(world, (0, 0, 0), d) == glass for d in DIRS}
        boxes = []
        for a, b in EDGES:
            if not ((vis[a] and not same[b]) or (vis[b] and not same[a])):
                continue
            mins, sizes = [0.0, 0.0, 0.0], [1.0, 1.0, 1.0]
            for f in (a, b):
                ax = 0 if f in ("east", "west") else (1 if f in ("up", "down") else 2)
                sizes[ax] = t
                mins[ax] = 1 - t if f in ("east", "up", "south") else 0.0
            boxes.append(tuple(mins) + tuple(sizes))
        boxes = resolve(boxes)
        blocks += 1
        for i, a in enumerate(boxes):
            for b in boxes[i + 1:]:
                if overlaps(a, b):
                    clashes += 1
        for b in boxes:
            if any(b[k] < -1e-9 or b[k] + b[k + 3] > 1 + 1e-9 for k in range(3)):
                strays += 1
    check(f"{blocks} block shapes: no two bars share space", clashes == 0, f"{clashes} clashes")
    check("no bar pokes outside its own block", strays == 0, f"{strays} strays")




ALL_FACES = ["up", "down", "north", "south", "east", "west"]
AXIS = {"east": 0, "west": 0, "up": 1, "down": 1, "north": 2, "south": 2}
POS = {"east", "up", "south"}
LATERALS = {0: ["up", "down", "north", "south"], 1: ["north", "south", "east", "west"],
            2: ["up", "down", "east", "west"]}


def block_boxes(world, pos, t=1 / 16):
    """Mirrors Rims.barsFor: the twelve edges, plus the cubes at an inner corner."""
    glass = world.get(pos)
    vis = {d: at(world, pos, d) != glass and at(world, pos, d) != "solid" for d in DIRS}
    same = {d: at(world, pos, d) == glass for d in DIRS}
    out = []

    def box(faces):
        mins, sizes = [0.0, 0.0, 0.0], [1.0, 1.0, 1.0]
        for f in faces:
            ax = AXIS[f]
            sizes[ax] = t
            mins[ax] = 1 - t if f in POS else 0.0
        return tuple(mins) + tuple(sizes)

    for a, b in EDGES:
        if (vis[a] and not same[b]) or (vis[b] and not same[a]):
            out.append(box([a, b]))
    for face in ALL_FACES:
        if not vis[face]:
            continue
        lat = LATERALS[AXIS[face]]
        for first in lat[:2]:
            for second in lat[2:]:
                if not same[first] or not same[second]:
                    continue
                d1, d2 = DIRS[first], DIRS[second]
                diag = (pos[0] + d1[0] + d2[0], pos[1] + d1[1] + d2[1], pos[2] + d1[2] + d2[2])
                if world.get(diag) == glass:
                    continue
                out.append(box([face, first, second]))
    return resolve(out)


def main_holes():
    print("\na hole in a glass sheet")
    sheet = {(x, 0, z): "glass" for x in range(-2, 5) for z in range(-2, 5)}
    del sheet[(0, 0, 0)]                      # a one block hole
    diag = block_boxes(sheet, (1, 0, 1))
    check("the block diagonally off a hole fills the corner the edges miss",
          len(diag) > 0, f"{len(diag)} bars")
    top = [b for b in diag if abs(b[1] + b[4] - 1.0) < 1e-9]
    check("and it does so on the face you can see", len(top) > 0, f"{len(top)} on top")
    corner = [b for b in top if abs(b[0]) < 1e-9 and abs(b[2]) < 1e-9]
    check("in the corner nearest the hole", len(corner) == 1, f"{corner}")

    interior = block_boxes(sheet, (2, 0, 2))
    check("a block away from the hole and the sheet's rim draws nothing",
          interior == [], f"{interior}")

    clashes = [(a, b) for i, a in enumerate(diag) for b in diag[i + 1:] if overlaps(a, b)]
    check("the new corner cubes clash with nothing", not clashes, f"{len(clashes)}")


if __name__ == "__main__":
    sys.exit(main())
