# GlassFrame

Glass with no borders for Minecraft Java 26.2, needing **no mods**. A window or a
floor reads as one clean sheet instead of a grid of outlined squares. Blocks and
panes both.

Download: [`GlassFrame-2.7.0-borderless.zip`](GlassFrame-2.7.0-borderless.zip) - 10 KB.

## Why most connected-glass packs do nothing

Vanilla draws a face unless the neighbour occludes it. Stone and glass both
occlude, so a resource pack can never ask *"is my neighbour glass?"*. That is why
nearly every connected-glass pack ships an `assets/minecraft/optifine/ctm` folder
and quietly does nothing at all without OptiFine or Continuity.

## Why this one has no border rather than a clever one

A model face may carry a `cullface` pointing somewhere other than the way it
faces - vanilla does this itself in 52 model faces. That lets a border strip be
erased by the neighbour beside it, which sounds like it should give a frame on
the rim and nothing inside.

It does not, and `test_culling.py` proves it. A strip needs two conditions at
once, *my side is visible* **and** *the surface does not continue this way*, and
a quad tests one. Whichever you keep, the strip reappears as a seam in some
other orientation: the frame that outlines a wall is the same geometry that
streaks a floor, one axis over. Checked across a floor and both wall
orientations, all 24 strips are a seam in at least one of them, and none
survives all three.

So the border goes entirely. Six full faces sampling only the inside of the
vanilla glass sprite, still culled against their own kind, so glass merges
exactly as vanilla does. The five pane templates are rebuilt without their
`#edge` pieces - the top rail and the end cap, which are precisely the dark line
between two connected panes.

No textures are shipped, only models, so another texture pack layered on top
still shows through.

## Getting the outline back

An outline that appears only where the glass genuinely stops needs both
neighbours known at once, which on a vanilla client only a server plugin can do.
`test_rim_rule.py` holds that rule and the shapes it has to satisfy: a stack of
slabs outlined on its top layer alone, no seam where two slabs meet, and a rim
against dirt.

## Building

`python3 build.py` writes `dist/` - the borderless build plus three others kept
as evidence. `python3 test_culling.py` replays Minecraft's culling rule over the
built models and asserts the results.
