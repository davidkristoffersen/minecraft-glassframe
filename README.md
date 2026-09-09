# GlassFrame

A connected-glass resource pack for Minecraft Java 26.2 that needs **no mods**.
A glass wall reads as one clear sheet with a frame only around its outer rim.

Download: [`GlassFrame-1.0.0.zip`](GlassFrame-1.0.0.zip) — 14 KB, models only.

## Why most connected-glass packs do nothing

Vanilla decides whether to draw a face by asking *"does the neighbour occlude
this side?"*. Stone and glass both answer yes, so a resource pack can never ask
*"is my neighbour glass?"*. That is why nearly every connected-glass pack ships
an `assets/minecraft/optifine/ctm` folder and quietly does nothing at all
without OptiFine or Continuity installed.

## What this does instead

A model face may carry a `cullface` pointing somewhere other than the way the
face itself points. Vanilla uses this in 52 of its own model faces
(`chorus_plant` is the well known one). Each side of a glass block is drawn as:

* **one centre quad**, inset 1px, culled by its own direction — so two glass
  blocks facing each other merge, exactly like vanilla;
* **four 1px border strips** along that side's edges, each culled by the
  neighbour it runs *towards*. The strip on the west edge of the north face is
  culled by the block to the **west**, so glass beside this one erases the line
  while the outside edge of the wall keeps its frame.

The handful of genuine vanilla packs cull those strips by the direction they
face, which is why a wall keeps a visible line at every join: the neighbour
beside you never removes a quad that points forwards.

No textures are shipped. The models sample the vanilla glass texture — the
interior for the centre, the 1px border ring for the strips — so the pack sits
happily on top of whatever other texture pack is loaded.

## Known limits

* **Glass 2+ blocks deep.** A quad tests one neighbour, but a border strip
  really wants two conditions: *my side is visible* **and** *the wall does not
  continue this way*. This keeps the second, so shared faces inside a solid
  glass volume still draw their strips, seen as faint outlines through the
  glass. Single-thickness windows and walls are exact.
* **Glass meeting stone** loses its frame line at that seam, because stone
  occludes exactly like glass does and the two cannot be told apart.
* **Panes are untouched, on purpose.** A pane's blockstate reads "connected"
  for a neighbouring pane and for solid dirt alike, so dropping its frame drops
  it against dirt too. Vanilla pane behaviour is the closest thing to correct.

## Building

`python3 build.py` writes `dist/`. `python3 test_culling.py` replays
Minecraft's culling rule over the built models for a lone block, a 3x3 wall,
glass against stone, a stacked column and mismatched stained glass, and asserts
the wall's front comes out bare inside with an unbroken rim.
