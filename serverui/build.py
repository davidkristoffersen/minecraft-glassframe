#!/usr/bin/env python3
"""
Build ServerUI: pixel icons for the server's menus, needing no mods.

What it does
------------
The dialog API gives a button a label and nothing else - no icon slot. Our menus
therefore start every label with a glyph (⚡ Actions, 🧩 Plugins, ▶ Try it) and
the vanilla client draws those from Unifont: a thin, monochrome, 16-pixel
fallback that reads as "some symbol" rather than as an icon.

A resource pack may add glyphs to the DEFAULT font, and the first provider that
knows a code point wins. So this pack registers an 8x8 pixel drawing at every
emoji and symbol code point the menus use, in front of the vanilla providers.
Every label keeps working exactly as before; a player with the pack sees an
icon where a player without it sees the Unifont symbol. Nothing is gated and no
Java changes.

Colour
------
Bitmap glyphs are multiplied by the text colour, like every letter. The icons
are therefore drawn in white and greys (four shades) and take the colour of the
label they sit in: the ⚙ in an AQUA settings label is aqua, the ⚠ in a RED
warning is red, a GOLD ★ is gold. That is the same rule the menus already use
for their glyph vocabulary, so one drawing serves every colour, and a label
that wants a fixed-colour icon simply colours that one character WHITE.

Geometry
--------
Cells are 8x8, `height` 8 and `ascent` 7, which is precisely the vanilla
letter grid: capitals fill rows 0-6, row 7 is the descender line. Icons stay in
rows 0-6 so they align with the text beside them, and every drawing is
left-aligned in its cell (the client trims trailing empty columns to find the
advance width, never leading ones). The client adds one pixel of spacing after
each glyph on its own.

Building
--------
`python3 build.py` reads the vanilla `font/default.json` from the installed
client jar (so the references to the vanilla providers are exactly the current
ones - nothing of Mojang's is vendored), writes `src/`, `dist/ServerUI-<v>.zip`
and `dist/preview.png` (the sheet at 6x on dark, for checking the art by eye).
"""

import binascii
import json
import pathlib
import shutil
import struct
import zipfile
import zlib

VERSION = "1.0.0"
HERE = pathlib.Path(__file__).parent
SRC = HERE / "src"
DIST = HERE / "dist"
CLIENT_JAR = pathlib.Path.home() / (
    "Library/Application Support/minecraft/versions/26.2/26.2.jar")
PACK_FORMAT_FALLBACK = 88

CELL = 8
PER_ROW = 16
# shade letters: '#' white, '+' light, '-' mid, '=' dark, '.' transparent
SHADES = {"#": 255, "+": 200, "-": 140, "=": 85}

# Every icon is at most 7 columns wide and 7 rows tall (rows 0-6); row 7 is the
# descender line and stays empty so icons sit on the same baseline as letters.
# Order and grouping mirror CLAUDE.md's glyph vocabulary, then hubs, then the
# rest - the sheet is only a texture, the order never matters to the client.
ART = {
    # ---- vocabulary
    "▶": ["##.....",
          "####...",
          "######.",
          "#######",
          "######.",
          "####...",
          "##....."],
    "▸": [".......",
          "##.....",
          "###....",
          "####...",
          "###....",
          "##.....",
          "......."],
    "✔": ["......#",
          ".....##",
          "....##.",
          "#..##..",
          "##.##..",
          ".###...",
          "..#...."],
    "✎": [".....##",
          "....#=#",
          "...#=#.",
          "..#=#..",
          ".#=#...",
          ".##....",
          "#-....."],
    "⚙": [".#.#.#.",
          ".#####.",
          "##...##",
          ".#...#.",
          "##...##",
          ".#####.",
          ".#.#.#."],
    "❓": [".#####.",
          "##...##",
          ".....##",
          "....##.",
          "...##..",
          ".......",
          "...##.."],
    "⚠": ["...#...",
          "..#.#..",
          "..#.#..",
          ".#.#.#.",
          ".#...#.",
          "#..#..#",
          "#######"],
    "★": ["...#...",
          "..###..",
          "#######",
          ".#####.",
          "..###..",
          ".##.##.",
          ".#...#."],
    "●": ["..###..",
          ".#####.",
          "#######",
          "#######",
          "#######",
          ".#####.",
          "..###.."],
    "○": ["..###..",
          ".#...#.",
          "#.....#",
          "#.....#",
          "#.....#",
          ".#...#.",
          "..###.."],
    "■": [".......",
          ".#####.",
          ".#####.",
          ".#####.",
          ".#####.",
          ".#####.",
          "......."],
    "▢": ["#######",
          "#.....#",
          "#.....#",
          "#.....#",
          "#.....#",
          "#.....#",
          "#######"],
    "•": [".......",
          ".......",
          "..##...",
          ".####..",
          ".####..",
          "..##...",
          "......."],
    "⟳": ["..###.#",
          ".#...##",
          "#...###",
          "#......",
          "#.....#",
          ".#...#.",
          "..###.."],
    "⟲": ["#.###..",
          "##...#.",
          "###...#",
          "......#",
          "#.....#",
          ".#...#.",
          "..###.."],
    "✖": ["#.....#",
          "##...##",
          ".##.##.",
          "..###..",
          ".##.##.",
          "##...##",
          "#.....#"],
    "✘": [".......",
          "##...##",
          ".##.##.",
          "..###..",
          ".##.##.",
          "##...##",
          "......."],
    "→": [".......",
          "...#...",
          "...##..",
          "#######",
          "...##..",
          "...#...",
          "......."],
    "✦": ["...#...",
          "...#...",
          "..###..",
          "#######",
          "..###..",
          "...#...",
          "...#..."],
    "✨": [".#.....",
          "###..#.",
          ".#..###",
          ".....#.",
          "..#....",
          ".###...",
          "..#...."],
    "＋": [".......",
          "...#...",
          "...#...",
          ".#####.",
          "...#...",
          "...#...",
          "......."],
    "ℹ": [".#####.",
          "#..#..#",
          "#.....#",
          "#..#..#",
          "#..#..#",
          "#..#..#",
          ".#####."],
    "⬆": ["...#...",
          "..###..",
          ".#####.",
          "#######",
          "..###..",
          "..###..",
          "..###.."],
    "⬇": ["..###..",
          "..###..",
          "..###..",
          "#######",
          ".#####.",
          "..###..",
          "...#..."],
    # ---- admin hubs
    "🧩": ["..##...",
           "..##...",
           "######.",
           "######.",
           "#######",
           "#######",
           "##..##."],
    "🎨": [".......",
           ".#####.",
           "#=#=###",
           "#######",
           "#=###.#",
           "###..##",
           ".#####."],
    "🌍": ["..###..",
           ".#=####",
           "#===###",
           "##=##=#",
           "###==##",
           ".####=.",
           "..###.."],
    "⚡": ["...###.",
           "..###..",
           ".###...",
           ".#####.",
           "...##..",
           "..##...",
           ".#....."],
    "🖥": ["#######",
           "#.....#",
           "#.....#",
           "#.....#",
           "#######",
           "...#...",
           ".#####."],
    "☠": [".#####.",
          "#######",
          "#=###=#",
          "#######",
          ".#####.",
          "..#.#..",
          "..###.."],
    "👁": [".......",
           "..###..",
           ".#+++#.",
           "##+=+##",
           ".#+++#.",
           "..###..",
           "......."],
    "🎒": ["..###..",
           ".#...#.",
           "#######",
           "#.....#",
           "#.###.#",
           "#.....#",
           ".#####."],
    "🧰": ["..###..",
           "..#.#..",
           "#######",
           "#.....#",
           "#######",
           "#.....#",
           "#######"],
    # ---- actions and settings
    "☀": ["#..#..#",
          ".#####.",
          ".#####.",
          "#######",
          ".#####.",
          ".#####.",
          "#..#..#"],
    "🌙": ["...###.",
           "..##...",
           ".##....",
           ".##....",
           ".##....",
           "..##...",
           "...###."],
    "🌤": ["#.#.#..",
           ".###...",
           "#####..",
           ".###.##",
           "#.#####",
           "..#####",
           "...###."],
    "🌧": ["..###..",
           ".######",
           "#######",
           ".#####.",
           ".#.#.#.",
           "#.#.#..",
           ".#.#.#."],
    "⛈": ["..###..",
          ".######",
          "#######",
          ".#####.",
          "...##..",
          "..###..",
          "...##.."],
    "🧪": [".#####.",
           "..#.#..",
           "..#.#..",
           "..#.#..",
           ".#+++#.",
           ".#+++#.",
           "..###.."],
    "💾": ["######.",
           "#.##.##",
           "#.##..#",
           "#.....#",
           "#.###.#",
           "#.###.#",
           "#######"],
    "👥": [".##....",
           ".##.##.",
           "....##.",
           ".###...",
           "####.##",
           "####.##",
           "####.##"],
    "👤": ["..###..",
           "..###..",
           "..###..",
           ".......",
           ".#####.",
           "#######",
           "#######"],
    "📜": [".######",
           "##....#",
           "#.###.#",
           "#.....#",
           "#.###.#",
           "#....##",
           "######."],
    "📖": [".......",
           "###.###",
           "#++#++#",
           "#++#++#",
           "#++#++#",
           "###.###",
           "......."],
    "🌐": ["..###..",
           ".#.#.#.",
           "#######",
           "#.#.#.#",
           "#######",
           ".#.#.#.",
           "..###.."],
    "🎲": [".#####.",
           "#=###=#",
           "#######",
           "###=###",
           "#######",
           "#=###=#",
           ".#####."],
    "🗑": ["..###..",
           "#######",
           ".#####.",
           ".#.#.#.",
           ".#.#.#.",
           ".#.#.#.",
           ".#####."],
    "⚖": ["...#...",
          "#######",
          ".#.#.#.",
          "#..#..#",
          "###.###",
          "...#...",
          "..###.."],
    "◎": ["..###..",
          ".#...#.",
          "#.###.#",
          "#.#.#.#",
          "#.###.#",
          ".#...#.",
          "..###.."],
    "⌖": ["...#...",
          "...#...",
          "..###..",
          "##.#.##",
          "..###..",
          "...#...",
          "...#..."],
    "♪": ["...##..",
          "...#.#.",
          "...#..#",
          "...#...",
          ".###...",
          "#####..",
          ".###..."],
    "⏹": [".......",
          ".#####.",
          ".#####.",
          ".#####.",
          ".#####.",
          ".#####.",
          "......."],
    "📣": [".....#.",
           "...###.",
           ".#####.",
           "######.",
           ".#####.",
           "...###.",
           "..#..#."],
    "🔊": ["...#..#",
           "..##...",
           "####.#.",
           "####..#",
           "####.#.",
           "..##...",
           "...#..#"],
    "❤": [".##.##.",
          "#######",
          "#######",
          "#######",
          ".#####.",
          "..###..",
          "...#..."],
    # ---- creatures (Haunt, MobSeats, Mob Designer)
    "🐴": [".#.....",
           "###....",
           "#####..",
           ".#####.",
           "..###.#",
           "..##...",
           "..##..."],
    "🐕": [".##....",
           ".###...",
           ".####..",
           "..#####",
           "..#####",
           "..#..#.",
           "..#..#."],
    "🐈": ["#...#..",
           "#####..",
           "#=#=#.#",
           "#####.#",
           ".####.#",
           ".######",
           ".#..#.."],
    "🦜": ["..###..",
           ".#=###.",
           "=#####.",
           "..####.",
           "..####.",
           "..###..",
           "..#...."],
    "🐾": [".#.#.#.",
           ".#.#.#.",
           ".......",
           ".#####.",
           "#######",
           "#######",
           ".#####."],
    "🧟": [".#####.",
           ".#=#=#.",
           ".#####.",
           ".##.##.",
           "#######",
           "#..#..#",
           "#..#..#"],
    "👻": ["..###..",
           ".#####.",
           ".#=#=#.",
           ".#####.",
           ".#####.",
           ".#####.",
           ".#.#.#."],
    "🍖": ["..###..",
           ".#####.",
           ".#####.",
           "..###..",
           "...##..",
           "...=#..",
           "....##."],
    # ---- Haunt categories
    "🌫": [".......",
           ".######",
           ".......",
           "######.",
           ".......",
           ".######",
           "......."],
    "🧬": ["######.",
           "#....#.",
           ".#..#..",
           "..##...",
           ".#..#..",
           "#....#.",
           "######."],
    "🫀": [".##.##.",
           "#######",
           "#######",
           "#######",
           ".#####.",
           "..###..",
           "...#..."],
    # ---- the odd Toolbox / shortcut glyphs that reach a menu label
    "🏆": ["#######",
           "#.###.#",
           "#.###.#",
           ".#####.",
           "..###..",
           "...#...",
           ".#####."],
    "🗺": ["#######",
           "#.....#",
           "#.##..#",
           "#...#.#",
           "#..##.#",
           "#.....#",
           "#######"],
    "🎥": [".##.##.",
           ".##.##.",
           "#####.#",
           "######.",
           "#####.#",
           ".#..#..",
           ".#..#.."],
    "📷": ["..##...",
           "#######",
           "#.###.#",
           "#.#=#.#",
           "#.###.#",
           "#######",
           "......."],
    "🔥": ["...#...",
           "..##...",
           "..###..",
           ".####..",
           ".#####.",
           ".#####.",
           "..###.."],
    "💬": [".######",
           "#.....#",
           "#.....#",
           "#.....#",
           ".#####.",
           ".##....",
           ".#....."],
    "💎": [".......",
           ".#####.",
           "#+#+#+#",
           "#######",
           ".#####.",
           "..###..",
           "...#..."],
    "🔔": ["...#...",
           "..###..",
           ".#####.",
           ".#####.",
           ".#####.",
           "#######",
           "...#..."],
    "🔮": ["..###..",
           ".#+###.",
           "#++####",
           "#+#####",
           ".#####.",
           "..###..",
           ".#####."],
    "🧊": [".#####.",
           "#+....#",
           "#+....#",
           "#+....#",
           "#+....#",
           "#++++++",
           ".#####."],
    "🍞": ["..####.",
           ".######",
           "#######",
           "######.",
           "#####..",
           "#####..",
           "......."],
}
# glyphs that share a drawing
ALIASES = {"↻": "⟳", "❔": "❓", "✅": "✔", "🎵": "♪"}


def _png_encode(w, h, rows):
    def chunk(tag, body):
        return (struct.pack(">I", len(body)) + tag + body
                + struct.pack(">I", binascii.crc32(tag + body) & 0xffffffff))
    raw = b"".join(b"\x00" + bytes(r) for r in rows)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def glyphs():
    """The full table, aliases resolved and every drawing checked and left-aligned."""
    table = dict(ART)
    for alias, target in ALIASES.items():
        table[alias] = ART[target]
    out = {}
    for ch, rows in table.items():
        if len(ch) != 1:
            raise ValueError(f"{ch!r} is not a single code point")
        if len(rows) > CELL:
            raise ValueError(f"{ch}: {len(rows)} rows, cell is {CELL}")
        for r in rows:
            if len(r) > CELL or set(r) - set(SHADES) - {"."}:
                raise ValueError(f"{ch}: bad row {r!r}")
        # left-align: leading empty columns would become padding the client keeps
        lead = min((len(r) - len(r.lstrip(".")) for r in rows if r.strip(".")), default=0)
        rows = [r[lead:] for r in rows]
        if not any(r.strip(".") for r in rows):
            raise ValueError(f"{ch}: empty drawing")
        out[ch] = rows
    return out


def sheet(table):
    """One RGBA texture, PER_ROW cells per line; returns (png bytes, chars rows)."""
    chars = list(table)
    lines = (len(chars) + PER_ROW - 1) // PER_ROW
    w, h = PER_ROW * CELL, lines * CELL
    rows = [bytearray(w * 4) for _ in range(h)]
    char_rows = []
    for line in range(lines):
        slice_ = chars[line * PER_ROW:(line + 1) * PER_ROW]
        for col, ch in enumerate(slice_):
            for y, art in enumerate(table[ch]):
                for x, px in enumerate(art):
                    if px == ".":
                        continue
                    v = SHADES[px]
                    i = ((col * CELL) + x) * 4
                    rows[line * CELL + y][i:i + 4] = bytes((v, v, v, 255))
        # code point 0 pads the line: the client skips it
        char_rows.append("".join(slice_) + chr(0) * (PER_ROW - len(slice_)))
    return _png_encode(w, h, rows), char_rows


def preview(table, scale=6):
    """The sheet at `scale` on dark, one cell of padding, for looking at the art."""
    chars = list(table)
    lines = (len(chars) + PER_ROW - 1) // PER_ROW
    pad = 2
    cw = (CELL + pad) * scale
    w, h = PER_ROW * cw, lines * cw
    bg = bytes((32, 34, 40, 255))
    rows = [bytearray(bg * w) for _ in range(h)]
    for n, ch in enumerate(chars):
        cx, cy = (n % PER_ROW) * cw, (n // PER_ROW) * cw
        for y, art in enumerate(table[ch]):
            for x, px in enumerate(art):
                if px == ".":
                    continue
                v = SHADES[px]
                for dy in range(scale):
                    row = rows[cy + (y + 1) * scale + dy]
                    for dx in range(scale):
                        i = (cx + (x + 1) * scale + dx) * 4
                        row[i:i + 4] = bytes((v, v, v, 255))
    return _png_encode(w, h, rows)


def pack_icon(table):
    """pack.png: four hub icons at 4x in their menu colours on a dark square."""
    picks = (("⚡", (255, 255, 85)), ("🧩", (85, 255, 255)),
             ("👁", (255, 85, 255)), ("🎒", (0, 170, 170)))
    scale, size = 4, 64
    rows = [bytearray(bytes((28, 30, 36, 255)) * size) for _ in range(size)]
    for n, (ch, (r, g, b)) in enumerate(picks):
        ox, oy = (n % 2) * 32, (n // 2) * 32
        for y, art in enumerate(table[ch]):
            for x, px in enumerate(art):
                if px == ".":
                    continue
                v = SHADES[px] / 255
                colour = bytes((int(r * v), int(g * v), int(b * v), 255))
                for dy in range(scale):
                    row = rows[oy + 2 + y * scale + dy]
                    for dx in range(scale):
                        i = (ox + 2 + x * scale + dx) * 4
                        row[i:i + 4] = colour
    return _png_encode(size, size, rows)


def vanilla_default_font():
    """The client's own font/default.json providers, so ours go in front of exactly
    what the running version ships. Falls back to the 26.x shape when the jar is
    not installed."""
    if CLIENT_JAR.exists():
        with zipfile.ZipFile(CLIENT_JAR) as jar:
            data = json.loads(jar.read("assets/minecraft/font/default.json"))
            fmt = json.loads(jar.read("version.json"))["pack_version"]["resource_major"]
        return data["providers"], fmt, True
    return [
        {"type": "reference", "id": "minecraft:include/space"},
        {"type": "reference", "id": "minecraft:include/default", "filter": {"uniform": False}},
        {"type": "reference", "id": "minecraft:include/unifont"},
    ], PACK_FORMAT_FALLBACK, False


def build(version=None):
    version = version or VERSION
    table = glyphs()
    if SRC.exists():
        shutil.rmtree(SRC)
    font_dir = SRC / "assets" / "minecraft" / "font"
    tex_dir = SRC / "assets" / "serverui" / "textures" / "font"
    font_dir.mkdir(parents=True)
    tex_dir.mkdir(parents=True)

    png, char_rows = sheet(table)
    (tex_dir / "icons.png").write_bytes(png)

    providers, fmt, from_jar = vanilla_default_font()
    ours = {"type": "bitmap", "file": "serverui:font/icons.png",
            "height": CELL, "ascent": 7, "chars": char_rows}
    (font_dir / "default.json").write_text(
        json.dumps({"providers": [ours] + providers}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")

    # 26.x reads min_format/max_format; a pack with only pack_format plus the
    # older supported_formats array shows as "incompatible or broken"
    (SRC / "pack.mcmeta").write_text(json.dumps({
        "pack": {
            "description": f"ServerUI {version}§7 - menu icons",
            "pack_format": fmt,
            "min_format": fmt,
            "max_format": 2147483647,
        }
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (SRC / "pack.png").write_bytes(pack_icon(table))

    DIST.mkdir(exist_ok=True)
    (DIST / "preview.png").write_bytes(preview(table))
    out = DIST / f"ServerUI-{version}.zip"
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(SRC.rglob("*")):
            if path.is_file():
                # fixed timestamps: the same art always gives the same sha1
                info = zipfile.ZipInfo(path.relative_to(SRC).as_posix(), (2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, path.read_bytes())
    return out, len(table), from_jar


if __name__ == "__main__":
    import hashlib
    out, count, from_jar = build()
    print(f"{out.name}: {count} glyphs, {out.stat().st_size} bytes, "
          f"sha1 {hashlib.sha1(out.read_bytes()).hexdigest()}"
          + ("" if from_jar else "  (client jar not found - vanilla providers assumed)"))
