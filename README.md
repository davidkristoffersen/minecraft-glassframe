# minecraft-resourcepacks

Server resource packs for a Paper 26.2 server, all working on a vanilla client
with **no mods**. Each folder is one pack: its `build.py`, its tests and the
current zip, which the server hands to players as an optional server resource
pack.

| Pack | What | Download |
|---|---|---|
| [GlassFrame](glassframe/) | Glass with no borders at all, blocks and panes, so a window or floor reads as one clean sheet. Pairs with a plugin that draws the outline back only where the glass actually stops. | [`GlassFrame-2.7.0-borderless.zip`](glassframe/GlassFrame-2.7.0-borderless.zip) |
| [ServerUI](serverui/) | Pixel icons at the emoji code points the server's dialog menus use, drawn into the default font. Without the pack the menus show the same symbols in Unifont. | [`ServerUI-1.0.0.zip`](serverui/ServerUI-1.0.0.zip) |

Every zip name carries its version: a new build is a new file and a new sha1,
so no client is ever served different bytes under a name it has cached.
