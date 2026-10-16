#!/usr/bin/env python3
"""
render_demo.py - render a terminal asciicast (v2) into an animated GIF.

Usage:
    python3 render_demo.py tools/demo.cast docs/demo.gif

The cast is produced by termtosvg (this repo's demo.cast was recorded with):
    { sleep 1; echo "python3 the_spiral.py --fast --live 1 --seconds 1"; \
      sleep 45; echo "exit"; } | python3 -m termtosvg record tools/demo.cast -g 104x30

Dependency: Pillow (only this tool, not the simulations).
"""

import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

# palette
DEFAULT_FG = (230, 237, 243)
DEFAULT_BG = (13, 17, 23)
BASE = {
    30: (36, 41, 46), 31: (255, 106, 105), 32: (86, 211, 100), 33: (255, 205, 90),
    34: (88, 166, 255), 35: (210, 132, 255), 36: (111, 220, 214), 37: (230, 237, 243),
}
BRIGHT = {
    90: (110, 118, 129), 91: (255, 123, 114), 92: (63, 225, 91), 93: (255, 212, 98),
    94: (105, 175, 255), 95: (219, 142, 255), 96: (125, 233, 223), 97: (255, 255, 255),
}
BASE_BG = {code + 10: rgb for code, rgb in BASE.items()}
BRIGHT_BG = {code + 10: rgb for code, rgb in BRIGHT.items()}


class Term:
    def __init__(self, cols, rows):
        self.cols, self.rows = cols, rows
        self.grid = [[(" ", DEFAULT_FG, DEFAULT_BG, False) for _ in range(cols)]
                     for _ in range(rows)]
        self.r = self.c = 0
        self.fg, self.bg, self.bold = DEFAULT_FG, DEFAULT_BG, False

    def scroll(self):
        self.grid.pop(0)
        self.grid.append([(" ", DEFAULT_FG, DEFAULT_BG, False) for _ in range(self.cols)])
        self.r = self.rows - 1

    def put(self, ch):
        if 0 <= self.r < self.rows and 0 <= self.c < self.cols:
            self.grid[self.r][self.c] = (ch, self.fg, self.bg, self.bold)
        self.c += 1
        if self.c >= self.cols:
            self.c = 0
            self.r += 1
            if self.r >= self.rows:
                self.scroll()

    def newline(self):
        self.c = 0
        self.r += 1
        if self.r >= self.rows:
            self.scroll()

    def sgr(self, params):
        i = 0
        while i < len(params):
            p = params[i]
            if p in BASE:
                self.fg = BASE[p]
            elif p in BRIGHT:
                self.fg = BRIGHT[p]
            elif p in BASE_BG:
                self.bg = BASE_BG[p]
            elif p in BRIGHT_BG:
                self.bg = BRIGHT_BG[p]
            elif p == 0:
                self.fg, self.bg, self.bold = DEFAULT_FG, DEFAULT_BG, False
            elif p == 1:
                self.bold = True
            elif p == 22:
                self.bold = False
            elif p == 39:
                self.fg = DEFAULT_FG
            elif p == 49:
                self.bg = DEFAULT_BG
            i += 1

    def erase_line(self, mode):
        if self.r >= self.rows:
            return
        if mode == 0:
            rng = range(self.c, self.cols)
        elif mode == 2:
            rng = range(self.cols)
        else:
            rng = range(0, self.c + 1)
        for x in rng:
            self.grid[self.r][x] = (" ", DEFAULT_FG, DEFAULT_BG, False)

    def clear(self):
        self.grid = [[(" ", DEFAULT_FG, DEFAULT_BG, False) for _ in range(self.cols)]
                     for _ in range(self.rows)]
        self.r = self.c = 0

    def feed(self, text):
        i = 0
        while i < len(text):
            ch = text[i]
            if ch == "\x1b" and i + 1 < len(text) and text[i + 1] == "[":
                j = i + 2
                while j < len(text) and not ("@" <= text[j] <= "~"):
                    j += 1
                if j >= len(text):
                    break
                raw = text[i + 2:j]
                fin = text[j]
                params = [int(x) if x else 0 for x in raw.replace("?", "").split(";")] if raw else [0]
                if fin == "m":
                    self.sgr(params)
                elif fin == "K":
                    self.erase_line(params[0] if params else 0)
                elif fin == "J":
                    self.clear()
                elif fin == "A":
                    self.r = max(0, self.r - (params[0] or 1))
                elif fin == "C":
                    self.c = min(self.cols - 1, self.c + (params[0] or 1))
                i = j + 1
                continue
            if ch == "\r":
                self.c = 0
            elif ch == "\n":
                self.newline()
            elif ch == "\b":
                self.c = max(0, self.c - 1)
            elif ch == "\t":
                self.c = min(self.cols - 1, (self.c // 8 + 1) * 8)
            elif ch >= " ":
                self.put(ch)
            i += 1

    def snapshot(self):
        return tuple(tuple(row) for row in self.grid)


def render(frames, out_path, font_path, cell_w=9, cell_h=18, font_px=14):
    font = ImageFont.truetype(font_path, font_px)
    cols, rows = frames[0][1].cols, frames[0][1].rows
    img_w, img_h = cols * cell_w, rows * cell_h
    images, durations = [], []
    prev_key, prev_t = None, None
    for t, term in frames:
        snap = term.snapshot()
        key = tuple(tuple(c for c, _, _, _ in row) for row in snap)
        if prev_key is not None and key == prev_key:
            durations[-1] += t - prev_t
        else:
            img = Image.new("RGB", (img_w, img_h), DEFAULT_BG)
            d = ImageDraw.Draw(img)
            for y, row in enumerate(snap):
                for x, (ch, fg, bg, bold) in enumerate(row):
                    px, py = x * cell_w, y * cell_h
                    if bg != DEFAULT_BG:
                        d.rectangle([px, py, px + cell_w - 1, py + cell_h - 1], fill=bg)
                    color = fg
                    if bold:
                        color = tuple(min(255, v + 30) for v in fg)
                    d.text((px, py), ch, font=font, fill=color)
            images.append(img)
            durations.append(t if prev_t is None else t - prev_t)
        prev_key, prev_t = key, t
    if not images:
        raise SystemExit("no frames rendered")
    durations = [max(int(d * 1000), 20) for d in durations]
    # quantize each frame BEFORE saving: passing palette args at save time with
    # RGB frames corrupts Pillow's multi-frame delta encoding (ghost frames)
    palette_images = [im.convert("P", palette=Image.ADAPTIVE, colors=128)
                      for im in images]
    palette_images[0].save(out_path, save_all=True, append_images=palette_images[1:],
                           duration=durations, loop=0, optimize=True)
    print(f"wrote {out_path}: {len(images)} frames, "
          f"{sum(durations) / 1000:.1f}s, {img_w}x{img_h}")


FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",  # linux
    "/usr/share/fonts/dejavu/DejaVuSansMono.ttf",           # linux (alt path)
    "/Library/Fonts/Menlo.ttc",                             # macos
    "/System/Library/Fonts/Menlo.ttc",                      # macos (system)
    "C:\\Windows\\Fonts\\consola.ttf",                      # windows
    "C:\\Windows\\Fonts\\cour.ttf",                         # windows (fallback)
]


def default_font():
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    sys.exit("no monospace font found; pass one explicitly: "
             "render_demo.py cast out.gif /path/to/font.ttf")


def main():
    cast_path, out_path = sys.argv[1], sys.argv[2]
    font_path = sys.argv[3] if len(sys.argv) > 3 else default_font()
    lines = open(cast_path, encoding="utf-8").read().splitlines()
    hdr = json.loads(lines[0])
    term = Term(hdr["width"], hdr["height"])
    frames = []
    last_t = 0.0
    for line in lines[1:]:
        t, _, data = json.loads(line)
        term.feed(data)
        if t - last_t >= 0.12:
            frames.append((t, Term(hdr["width"], hdr["height"])))
            frames[-1][1].grid = [list(r) for r in term.grid]
            frames[-1][1].r, frames[-1][1].c = term.r, term.c
            frames[-1][1].fg, frames[-1][1].bg, frames[-1][1].bold = \
                term.fg, term.bg, term.bold
            last_t = t
    frames.append((json.loads(lines[-1])[0], frames[-1][1]))
    render(frames, out_path, font_path)


if __name__ == "__main__":
    main()
