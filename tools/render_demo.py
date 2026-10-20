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

# Resource budgets and parser policy (security audit round 9, AS-02/03/04).
# A demo recording is ~130 KB / ~50 s; the budgets below are hundreds of
# times larger than any legitimate cast, and every over-budget input gets a
# clean error instead of unbounded work.
MAX_INPUT_BYTES = 32 * 1024 * 1024      # whole cast file
MAX_LINE_BYTES = 1024 * 1024            # one event line (escape-sequence bomb)
MAX_EVENTS = 500_000                    # event lines
MAX_CELLS = 100_000                     # terminal grid cells (per snapshot)
MAX_SAMPLES = 20_000                    # retained snapshots
# Cell-snapshots bound the parser's real memory amplifier (every snapshot is
# a full grid copy): 4M cell-snapshots ~= 280 MB of tuples worst case, and
# the shipped demo itself is ~1.3M.
MAX_CELLS_TOTAL = 4_000_000
# Timestamp domain: recordings are minutes; one year is generous. Enforcing
# it at parse time keeps derived frame-delay arithmetic (hold * 1000) far
# from float overflow (1e308-style timestamps, AS-03).
MAX_TIMESTAMP = 31_536_000.0            # 365 days, seconds
# A single CSI parameter carries at most 19 digits: larger values are
# clamped by the cursor-move bounds anyway, and 4300+-digit strings trip
# Python's int-conversion safeguard (ValueError mid-parse, AS-02). A
# parameter string longer than this makes the WHOLE sequence ignored.
MAX_CSI_PARAM_DIGITS = 19
MAX_CSI_RAW = 256
# An escape sequence split across feed() chunks is held in `pending`; cap it
# so a never-terminating CSI/OSC stream can't grow parser state without
# bound. The cap is dropped (the sequence is abandoned), which is safe: all
# bytes inside an unterminated CSI/OSC are parameter payload, never
# renderable text.
MAX_PENDING = 4096


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

    def _hold(self, seq):
        # Buffer an incomplete escape sequence across feed() calls, but only
        # up to MAX_PENDING bytes — an unterminated CSI/OSC stream must not
        # grow parser state without bound (AS-02). When the cap drops payload
        # bytes, keep the ESC + introducer so the sequence still completes
        # (and is then ignored as over-long) instead of leaking its tail
        # bytes onto the screen as plain text.
        if len(seq) > MAX_PENDING:
            self.pending = seq[:2] + seq[-(MAX_PENDING - 2):]
        else:
            self.pending = seq

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
                    self._hold(text[i:])
                    break
                raw = text[i + 2:j]
                fin = text[j]
                if len(raw) > MAX_CSI_RAW:
                    # oversized parameter string: consume the sequence but
                    # apply nothing (parser policy, AS-02)
                    i = j + 1
                    continue
                # unknown/non-numeric/over-long parameters (e.g. ESC[!p)
                # degrade to 0; >19-digit strings never reach int() (AS-02)
                params = [int(x) if x.isdigit() and len(x) <= MAX_CSI_PARAM_DIGITS
                          else 0 for x in raw.replace("?", "").split(";")] if raw else [0]
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
                    self._hold(text[i:])
                    break
                if j == esc:
                    if j + 1 < n and text[j + 1] == "\\":
                        i = j + 2  # ST: consume ESC and backslash
                        continue
                    if j + 1 >= n:
                        # ESC is the last byte: it may be the first half of
                        # an ST split across chunks — wait for more input
                        self._hold(text[i:])
                        break
                    i = j  # a different sequence: reprocess from the ESC
                    continue
                i = j + 1  # BEL
                continue
            if ch == "\x1b":
                if i + 1 >= n:
                    self._hold(text[i:])  # lone ESC at chunk end
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
        # GIF frame delays are 16-bit; clamp the hold to the documented
        # 0.02s..600s window BEFORE int() so extreme (or, defense in depth,
        # non-finite) floats can never overflow the conversion (AS-03)
        ms = int(min(max(hold, 0.0), 600.0) * 1000)
        ms = min(max(ms, 20), 600_000)
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
        if os.path.getsize(cast_path) > MAX_INPUT_BYTES:
            sys.exit(f"cast file too large in {cast_path}: over "
                     f"{MAX_INPUT_BYTES} bytes (resource budget, AS-04)")
        cast = open(cast_path, encoding="utf-8")
    except UnicodeDecodeError as e:
        sys.exit(f"cannot decode {cast_path} as UTF-8: {e}")
    except OSError as e:
        sys.exit(f"cannot read {cast_path}: {e}")
    with cast:
        try:
            header_line = cast.readline()
        except UnicodeDecodeError as e:
            sys.exit(f"cannot decode {cast_path} as UTF-8: {e}")
        try:
            hdr = json.loads(header_line)
        except ValueError as e:
            sys.exit(f"malformed cast header in {cast_path}: {e}")
        if not isinstance(hdr, dict):
            sys.exit(f"malformed cast header in {cast_path}: not a JSON object")
        try:
            cols, rows = hdr["width"], hdr["height"]
        except KeyError as e:
            sys.exit(f"malformed cast header in {cast_path}: missing {e}")
        # A terminal grid is allocated per event snapshot, so hostile
        # dimensions are the renderer's main memory/CPU amplifier: a 44-byte
        # cast claiming 100000x100000 cells never finishes. Require true
        # integers and bound the total grid (the largest realistic
        # recordings are ~300x100).
        if (isinstance(cols, bool) or isinstance(rows, bool)
                or not isinstance(cols, int) or not isinstance(rows, int)
                or cols < 1 or rows < 1 or cols * rows > MAX_CELLS):
            sys.exit(f"malformed cast header in {cast_path}: width/height must be "
                     f"positive integers totaling at most {MAX_CELLS} cells, "
                     f"got {cols!r} x {rows!r}")
        term = Term(cols, rows)
        samples = []   # (timestamp, snapshot)
        last_t, prev_t, final_t, n_events = 0.0, 0.0, 0.0, 0
        for n, line in enumerate(cast, 2):
            if len(line.encode("utf-8", "ignore")) > MAX_LINE_BYTES:
                sys.exit(f"cast line {n} in {cast_path} exceeds the "
                         f"{MAX_LINE_BYTES}-byte event budget (AS-04)")
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except ValueError as e:
                sys.exit(f"malformed cast event line {n} in {cast_path}: {e}")
            # AS-01: validate the event's structure and field types before
            # unpacking — JSON scalars (null/true/numbers/strings) used to
            # raise an uncaught TypeError here.
            if not isinstance(event, list) or len(event) != 3:
                sys.exit(f"malformed cast event line {n} in {cast_path}: "
                         f"expected [time, type, data], got {event!r:.200}")
            t, ev, data = event
            if isinstance(t, bool) or not isinstance(t, (int, float)):
                sys.exit(f"malformed timestamp on cast line {n} in {cast_path}: {t!r}")
            if not math.isfinite(t):
                sys.exit(f"non-finite timestamp on cast line {n} in {cast_path}: {t}")
            # AS-03: documented timestamp domain — finite, non-negative, at
            # most one year, and non-decreasing (asciicast v2 ordering).
            if not 0.0 <= t <= MAX_TIMESTAMP:
                sys.exit(f"timestamp out of range on cast line {n} in {cast_path}: "
                         f"{t} (allowed 0..{MAX_TIMESTAMP:.0f})")
            if t < prev_t:
                sys.exit(f"timestamp out of order on cast line {n} in {cast_path}: "
                         f"{t} after {prev_t}")
            prev_t = t
            if not isinstance(ev, str):
                sys.exit(f"malformed event code on cast line {n} in {cast_path}: "
                         f"expected string, got {type(ev).__name__}")
            if ev != "o":
                continue   # input, markers, resize: not terminal output
            if not isinstance(data, str):
                sys.exit(f"malformed event data on cast line {n} in {cast_path}: "
                         f"expected string, got {type(data).__name__}")
            n_events += 1
            if n_events > MAX_EVENTS:
                sys.exit(f"cast event budget exceeded in {cast_path}: over "
                         f"{MAX_EVENTS} output events (AS-04)")
            term.feed(data)
            final_t = max(final_t, t)
            if t - last_t >= 0.12:
                # AS-04: snapshots are full grid copies; cap both their count
                # and the total retained cells so hostile casts get a clean
                # error instead of unbounded memory.
                if (len(samples) >= MAX_SAMPLES
                        or (len(samples) + 1) * cols * rows > MAX_CELLS_TOTAL):
                    sys.exit(f"cast exceeds the supported rendering workload in "
                             f"{cast_path}: over {MAX_SAMPLES} frames or "
                             f"{MAX_CELLS_TOTAL} cell-frames (AS-04)")
                samples.append((t, term.snapshot()))
                last_t = t
    # always include the true final terminal state, even on a short cast
    samples.append((max(final_t, samples[-1][0] if samples else 0.0),
                    term.snapshot()))
    render(samples, out_path, font_path)


if __name__ == "__main__":
    main()
