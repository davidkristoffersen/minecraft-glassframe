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


def pane_boxes(world, pos, t=2 / 16):
    """The actual boxes, mirroring Rims.paneBars, as (minX,minY,minZ,sizeX,sizeY,sizeZ)."""
    me = world[pos]
    conn = {d: connects(at(world, pos, d)) for d in SIDES}
    n, s, e, w = conn["north"], conn["south"], conn["east"], conn["west"]
    across = min(t, HI - LO)     # a bar is its own thickness across the sheet, centred
    mid = (LO + HI) / 2 - across / 2
    minX, maxX = (0 if w else LO), (1 if e else HI)
    minZ, maxZ = (0 if n else LO), (1 if s else HI)
    along_x, along_z = e or w, n or s
    out = []
    if not along_x and not along_z:
        # one solid bar the size of the post - see Rims.paneBars
        return [(LO, 0, LO, HI - LO, 1, HI - LO)]

    def covered_along(vertical, x_axis):
        """How much of this block the pane above/below actually sits over - its own post
        plus whichever arms it reaches out with - or None if there is no pane there."""
        d = (0, 1, 0) if vertical == "up" else (0, -1, 0)
        npos = (pos[0] + d[0], pos[1] + d[1], pos[2] + d[2])
        if world.get(npos) != me:
            return None
        c = {s: connects(at(world, npos, s)) for s in SIDES}
        return ((0 if c["west"] else LO), (1 if c["east"] else HI)) if x_axis \
            else ((0 if c["north"] else LO), (1 if c["south"] else HI))

    def uncovered(a, b, cover):
        """Each cut end reaches one pane-thickness into the cover, so the rail tucks under
        whatever rises there instead of stopping on its edge and leaving a corner hole."""
        if cover is None:
            return [(a, b)] if b - a > 1e-4 else []
        reach = HI - LO
        runs = []
        if cover[0] - a > 1e-4:
            runs.append((a, min(cover[0] + reach, b)))
        if b - cover[1] > 1e-4:
            runs.append((max(cover[1] - reach, a), b))
        return runs

    for top in (True, False):
        vert = "up" if top else "down"
        if not along_x and not along_z and at(world, pos, vert) == me:
            continue
        y = 1 - t if top else 0
        cover_x, cover_z = covered_along(vert, True), covered_along(vert, False)
        along_the_x = uncovered(minX, maxX, cover_x) if along_x else []
        for a, b in along_the_x:
            out.append((a, y, mid, b - a, t, across))
        # the Z rail only skips the post while an X rail actually survives over it
        x_owns_post = any(a <= LO + 1e-4 and b >= HI - 1e-4 for a, b in along_the_x)
        if along_z:
            spans = ([(minZ, LO)] if n else []) + ([(HI, maxZ)] if s else []) \
                if (along_x and x_owns_post) else [(minZ, maxZ)]
            for span in spans:
                for a, b in uncovered(span[0], span[1], cover_z):
                    out.append((mid, y, a, across, t, b - a))
    perp = {"north": ("east", "west"), "south": ("east", "west"),
            "east": ("north", "south"), "west": ("north", "south")}
    for d in SIDES:
        pos_side = d in ("east", "south")
        straight = (not conn[d] and conn[OPP[d]]
                    and not conn[perp[d][0]] and not conn[perp[d][1]])
        width = t                # same thickness as every other bar; at t = 2px it fills the post
        if conn[d]:
            if at(world, pos, d) == me:
                continue
            a = 1 - width if pos_side else 0
        elif straight:
            a = mid
        else:
            continue
        if d in ("east", "west"):
            out.append((a, 0, mid, width, 1, across))
        else:
            out.append((mid, 0, a, across, 1, width))
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
        """True only when the pane there covers this block's whole span - a partial cover
        leaves a run of rail behind, which pane_boxes works out exactly."""
        d = (0, 1, 0) if vertical == "up" else (0, -1, 0)
        npos = (pos[0] + d[0], pos[1] + d[1], pos[2] + d[2])
        if world.get(npos) != me:
            return False
        c = {s: connects(at(world, npos, s)) for s in SIDES}
        return (c["east"] and c["west"]) if x_axis else (c["north"] and c["south"])

    for end in ("up", "down"):
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
    check("a pane on its own is one solid bar, like a wall's end cap", len(lone) == 1,
          f"{len(lone)} bars")
    bar = lone[0]
    check("filling the post, full height",
          abs(bar[3] - (HI - LO)) < 1e-9 and abs(bar[5] - (HI - LO)) < 1e-9
          and abs(bar[4] - 1) < 1e-9, f"{bar}")
    stacked = resolve(pane_boxes({(0, 0, 0): "pane", (0, 1, 0): "pane"}, (0, 0, 0)))
    check("and stacked lone panes still make one continuous column",
          len(stacked) == 1 and abs(stacked[0][4] - 1) < 1e-9, f"{stacked}")

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

    print("\na wall whose upper course stops early")
    # ground PPP with an arm south of the middle, one course above only PP
    stepped = {(1, 0, 0): "pane", (2, 0, 0): "pane", (3, 0, 0): "pane",
               (2, 0, 1): "pane", (1, 1, 0): "pane", (2, 1, 0): "pane"}
    two = [b for b in resolve(pane_boxes(stepped, (2, 0, 0)))
           if b[4] < 0.5 and abs(b[1] + b[4] - 1) < 1e-9 and abs(b[2] - LO) < 1e-9]
    three = [b for b in resolve(pane_boxes(stepped, (3, 0, 0)))
             if b[4] < 0.5 and abs(b[1] + b[4] - 1) < 1e-9 and abs(b[2] - LO) < 1e-9]
    check("the block under the end of the upper course keeps the rest of its rail",
          len(two) == 1 and two[0][0] <= HI + 1e-9
          and abs(two[0][0] + two[0][3] - 1) < 1e-9, f"{two}")
    check("and it meets the next block's rail with no gap",
          len(three) == 1 and abs(three[0][0]) < 1e-9, f"{three}")
    covered = [b for b in resolve(pane_boxes(stepped, (1, 0, 0)))
               if b[4] < 0.5 and abs(b[1] + b[4] - 1) < 1e-9 and abs(b[2] - LO) < 1e-9]
    check("a block fully under the upper course still draws no top rail",
          covered == [], f"{covered}")

    print("\nthe corner where a rail meets something standing on it")
    # a wall stepping up to the east, with an arm running north from the step
    step = {(6, 0, 0): "pane", (7, 0, 0): "pane", (8, 0, 0): "pane", (7, 0, -1): "pane",
            (7, 1, 0): "pane", (8, 1, 0): "pane"}
    rails = [b for b in resolve(pane_boxes(step, (7, 0, 0)))
             if b[4] < 0.5 and abs(b[1] + b[4] - 1) < 1e-9]
    along_x = [b for b in rails if abs(b[2] - LO) < 1e-9]
    check("the rail reaches the post rather than stopping on the covered strip",
          len(along_x) == 1 and along_x[0][0] + along_x[0][3] >= HI - 1e-9,
          f"{along_x}")
    corner_filled = any(b[0] <= LO + 1e-9 <= b[0] + b[3] and b[2] <= LO + 1e-9 <= b[2] + b[5]
                        for b in rails)
    check("so the corner cube under the step is covered", corner_filled, f"{rails}")

    standing = {(22, 0, 0): "pane", (23, 0, 0): "pane", (22, 1, 0): "pane"}
    rails = [b for b in resolve(pane_boxes(standing, (22, 0, 0)))
             if b[4] < 0.5 and abs(b[1] + b[4] - 1) < 1e-9]
    check("and a pane standing on a wall no longer breaks its rail",
          len(rails) == 1 and abs(rails[0][0] - LO) < 1e-9
          and abs(rails[0][0] + rails[0][3] - 1) < 1e-9, f"{rails}")

    print("\nsomething always has to own the post")
    # a corner with the upper course carrying on east over it: the X rail is fully
    # covered, so the Z rail has to run through the post instead of skipping it
    over = {(24, 0, 0): "pane", (25, 0, 0): "pane", (24, 0, 1): "pane",
            (24, 1, 0): "pane", (25, 1, 0): "pane"}
    tops = [b for b in resolve(pane_boxes(over, (24, 0, 0)))
            if b[4] < 0.5 and abs(b[1] + b[4] - 1) < 1e-9]
    covered = [b for b in tops
               if b[0] <= LO + 1e-4 <= b[0] + b[3] and b[2] <= LO + 1e-4 <= b[2] + b[5]]
    check("the corner is covered even when the X rail is entirely gone",
          len(covered) == 1, f"tops={tops}")

    # and where the X rail does survive, the Z rail still keeps off it
    plain = {(0, 0, 0): "pane", (1, 0, 0): "pane", (0, 0, 1): "pane"}
    boxes = resolve(pane_boxes(plain, (0, 0, 0)))
    clash = [(a, b) for i, a in enumerate(boxes) for b in boxes[i + 1:] if overlaps(a, b)]
    check("without stacking on it, the two rails still do not overlap", not clash,
          f"{len(clash)} clashes")

    print("\nan upright has to meet a rail square on")
    odd = []
    import itertools
    for mask in itertools.product([None, "pane", "solid"], repeat=4):
        world = {(0, 0, 0): "pane"}
        for side, val in zip(SIDES, mask):
            if val:
                world[DIRS[side]] = val
        for b in resolve(pane_boxes(world, (0, 0, 0))):
            thin = sorted(b[3:])[:2]        # the two small dimensions of this bar
            if any(abs(d - (HI - LO)) > 1e-9 for d in thin):
                odd.append((mask, b))
    check("at the default thickness every bar has the same square section",
          not odd, f"{len(odd)} odd, e.g. {odd[0] if odd else ''}")

    # The same sweep at a hairline thickness. 2px is the default because it fills the
    # post exactly, but a thinner bar has to hold together too: centred on the sheet
    # rather than flush with one face of it, still square, still inside its own block
    # and still not sharing space with the bar it meets at a corner.
    thin_odd, thin_clash, thin_stray = [], [], []
    for mask in itertools.product([None, "pane", "solid"], repeat=4):
        world = {(0, 0, 0): "pane"}
        for side, val in zip(SIDES, mask):
            if val:
                world[DIRS[side]] = val
        boxes = resolve(pane_boxes(world, (0, 0, 0), t=1 / 16))
        for b in boxes:
            thin = sorted(b[3:])[:2]
            if any(abs(d - 1 / 16) > 1e-9 for d in thin) and len(boxes) > 1:
                thin_odd.append((mask, b))
            if any(v < -1e-6 for v in b[:3]) or any(b[i] + b[i + 3] > 1 + 1e-6 for i in range(3)):
                thin_stray.append((mask, b))
        thin_clash += [(a, b) for i, a in enumerate(boxes) for b in boxes[i + 1:]
                       if overlaps(a, b)]
    check("a 1px outline is square too, not flush with one face of the sheet",
          not thin_odd, f"{len(thin_odd)} odd, e.g. {thin_odd[0] if thin_odd else ''}")
    check("a 1px outline stays inside its own block", not thin_stray,
          f"{len(thin_stray)} strays")
    check("a 1px outline does not overlap itself either", not thin_clash,
          f"{len(thin_clash)} overlapping pairs")

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
