# ServerUI

Pixel icons for a Paper server's dialog menus, for Minecraft Java 26.2+, needing
**no mods**. 2 KB.

Download: [`ServerUI-1.0.0.zip`](ServerUI-1.0.0.zip)

## What it does

The dialog API gives a button a label and nothing else - there is no icon slot.
So a server that wants icons starts every label with a glyph (`⚡ Actions`,
`🧩 Plugins`, `▶ Try it`), and a vanilla client draws those from Unifont: a
thin, monochrome 16-pixel fallback that reads as "some symbol".

A resource pack may add glyphs to the **default** font, and the first provider
that knows a code point wins. This pack registers an 8x8 drawing at 81 emoji
and symbol code points, in front of the vanilla providers. A player with the
pack sees an icon; a player without it sees the symbol they saw before. Nothing
is gated and the server code is unchanged.

## Colour

Bitmap glyphs are multiplied by the text colour, exactly like letters. The
icons are drawn in white and greys and take the colour of the label they sit
in: an aqua settings label gets an aqua ⚙, a red warning a red ⚠, a gold ★ is
gold. One drawing serves every colour.

## Geometry

Cells are 8x8 with `ascent` 7 - the vanilla letter grid. Icons fill rows 0-6,
which is where capitals sit, so they align with the text beside them.

## Building

`python3 build.py` reads the vanilla `font/default.json` out of the installed
client jar (so our provider goes in front of exactly the references the running
version ships - nothing of Mojang's is vendored), then writes `src/`,
`dist/ServerUI-<version>.zip` and `dist/preview.png`, the whole sheet at 6x for
checking the art by eye. The art itself is the `ART` table in `build.py`: one
string per row, `#` `+` `-` `=` for four shades, `.` for transparent.
