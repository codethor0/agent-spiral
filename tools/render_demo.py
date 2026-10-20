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
import math
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
        self.pending = ""        # incomplete escape sequence across feed() calls
        self.wrap_pending = False  # deferred autowrap at the right margin

    def scroll(self):
        self.grid.pop(0)
        self.grid.append([(" ", DEFAULT_FG, DEFAULT_BG, False) for _ in range(self.cols)])
        self.r = self.rows - 1

    def put(self, ch):
        if self.wrap_pending:
            self.wrap_pending = False
            self.newline()
        if 0 <= self.r < self.rows and 0 <= self.c < self.cols:
            self.grid[self.r][self.c] = (ch, self.fg, self.bg, self.bold)
        if self.c >= self.cols - 1:
            self.c = self.cols - 1
            self.wrap_pending = True   # stay on the last column until the next char
        else:
            self.c += 1

    def newline(self):
        self.c = 0
        self.wrap_pending = False
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
        # re-attach an escape sequence split across feed() calls
        text = self.pending + text
        self.pending = ""
        i = 0
        n = len(text)
        while i < n:
            ch = text[i]
            if ch == "\x1b" and i + 1 < n and text[i + 1] == "[":
                j = i + 2
                while j < n and not ("@" <= text[j] <= "~"):
                    j += 1
                if j >= n:
                    self.pending = text[i:]
                    break
                raw = text[i + 2:j]
                fin = text[j]
                # unknown/non-numeric parameters (e.g. ESC[!p) degrade to 0
                params = [int(x) if x.isdigit() else 0
                          for x in raw.replace("?", "").split(";")] if raw else [0]
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
                # other final bytes (p, H, etc.): consumed, not rendered
                i = j + 1
                continue
            if ch == "\x1b" and i + 1 < n and text[i + 1] == "]":
                # OSC (title, etc.): terminated by BEL or ST (ESC \). Find
                # the EARLIEST of the two so a later BEL can't swallow
                # output that follows an ST in the same chunk.
                bel = text.find("\a", i + 2)
                esc = text.find("\x1b", i + 2)
                j = bel if (esc < 0 or 0 <= bel < esc) else esc
                if j < 0:
                    # unterminated: keep the WHOLE OSC (not just the tail)
                    # so a terminator split across chunks is reassembled
                    self.pending = text[i:]
                    break
                if j == esc:
                    if j + 1 < n and text[j + 1] == "\\":
                        i = j + 2  # ST: consume ESC and backslash
                        continue
                    if j + 1 >= n:
                        # ESC is the last byte: it may be the first half of
                        # an ST split across chunks — wait for more input
                        self.pending = text[i:]
                        break
                    i = j  # a different sequence: reprocess from the ESC
                    continue
                i = j + 1  # BEL
                continue
            if ch == "\x1b":
                if i + 1 >= n:
                    self.pending = text[i:]  # lone ESC at chunk end
                    break
                i += 1  # unsupported two-byte sequence: drop the ESC
                continue
            self.wrap_pending = False if ch in "\r\n\b" else self.wrap_pending
            if ch == "\r":
                self.c = 0
            elif ch == "\n":
                self.newline()
            elif ch == "\b":
                self.c = max(0, self.c - 1)
                self.wrap_pending = False
            elif ch == "\t":
                self.c = min(self.cols - 1, (self.c // 8 + 1) * 8)
            elif ch >= " ":
                self.put(ch)
            i += 1

    def snapshot(self):
        return tuple(tuple(row) for row in self.grid)


def render(samples, out_path, font_path, cell_w=9, cell_h=18, font_px=14):
    if not samples:
        raise SystemExit("no frames rendered")
    # a screen is visible from its own timestamp until the next screen's
    # timestamp; the final screen holds for the tail of the recording
    holds = [samples[i + 1][0] - samples[i][0] for i in range(len(samples) - 1)]
    tail = samples[-1][0] - samples[-2][0] if len(samples) > 1 else 1.0
    holds.append(max(tail, 1.0))
    # merge consecutive identical screens (full state: chars + colors + bold)
    screens = []  # [snapshot, total_ms]
    for (_, snap), hold in zip(samples, holds):
        # GIF frame delays are 16-bit; clamp pathological holds (e.g. a
        # hostile cast with a years-long final gap) instead of erroring
        ms = min(max(int(hold * 1000), 20), 600_000)
        if screens and screens[-1][0] == snap:
            screens[-1][1] += ms
        else:
            screens.append([snap, ms])
    font = ImageFont.truetype(font_path, font_px)
    cols, rows = len(screens[0][0][0]), len(screens[0][0])
    img_w, img_h = cols * cell_w, rows * cell_h
    images, durations = [], []
    for snap, ms in screens:
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
        durations.append(ms)
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
    if len(sys.argv) < 3:
        print("usage: render_demo.py cast out.gif [font.ttf]", file=sys.stderr)
        sys.exit(2)
    cast_path, out_path = sys.argv[1], sys.argv[2]
    font_path = sys.argv[3] if len(sys.argv) > 3 else default_font()
    try:
        lines = open(cast_path, encoding="utf-8").read().splitlines()
    except UnicodeDecodeError as e:
        sys.exit(f"cannot decode {cast_path} as UTF-8: {e}")
    except OSError as e:
        sys.exit(f"cannot read {cast_path}: {e}")
    try:
        hdr = json.loads(lines[0])
    except (IndexError, ValueError) as e:
        sys.exit(f"malformed cast header in {cast_path}: {e}")
    if not isinstance(hdr, dict):
        sys.exit(f"malformed cast header in {cast_path}: not a JSON object")
    try:
        cols, rows = hdr["width"], hdr["height"]
    except KeyError as e:
        sys.exit(f"malformed cast header in {cast_path}: missing {e}")
    # A terminal grid is allocated per event snapshot, so hostile dimensions
    # are the renderer's main memory/CPU amplifier: a 44-byte cast claiming
    # 100000x100000 cells never finishes. Require true integers and bound
    # the total grid (the largest realistic recordings are ~300x100).
    MAX_CELLS = 100_000
    if (isinstance(cols, bool) or isinstance(rows, bool)
            or not isinstance(cols, int) or not isinstance(rows, int)
            or cols < 1 or rows < 1 or cols * rows > MAX_CELLS):
        sys.exit(f"malformed cast header in {cast_path}: width/height must be "
                 f"positive integers totaling at most {MAX_CELLS} cells, "
                 f"got {cols!r} x {rows!r}")
    term = Term(cols, rows)
    samples = []   # (timestamp, snapshot)
    last_t, final_t = 0.0, 0.0
    for n, line in enumerate(lines[1:], 2):
        if not line.strip():
            continue
        try:
            t, ev, data = json.loads(line)
        except ValueError as e:
            sys.exit(f"malformed cast event line {n} in {cast_path}: {e}")
        if ev != "o":
            continue   # input, markers, resize: not terminal output
        try:
            t = float(t)
        except (TypeError, ValueError):
            sys.exit(f"malformed timestamp on cast line {n} in {cast_path}: {t!r}")
        if not math.isfinite(t):
            sys.exit(f"non-finite timestamp on cast line {n} in {cast_path}: {t}")
        if not isinstance(data, str):
            sys.exit(f"malformed event data on cast line {n} in {cast_path}: "
                     f"expected string, got {type(data).__name__}")
        term.feed(data)
        final_t = max(final_t, t)
        if t - last_t >= 0.12:
            samples.append((t, term.snapshot()))
            last_t = t
    # always include the true final terminal state, even on a short cast
    samples.append((max(final_t, samples[-1][0] if samples else 0.0),
                    term.snapshot()))
    render(samples, out_path, font_path)


if __name__ == "__main__":
    main()
