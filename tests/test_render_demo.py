#!/usr/bin/env python3
"""
test_render_demo.py — unit tests for the terminal renderer in tools/render_demo.py.

Run with the main suite:
    python3 -m unittest discover -s tests

These tests import the renderer directly and exercise the escape-sequence
edge cases called out in the audit: OSC terminated by BEL vs ST (ESC \\),
sequences split across feed chunks, deferred autowrap, and CLI validation.

Requires Pillow (same optional dependency as render_demo.py); skipped if
Pillow is not installed.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))
    import render_demo
    HAS_PIL = True
except ImportError:
    render_demo = None
    HAS_PIL = False


def row_text(term, r=0):
    return "".join(c[0] for c in term.grid[r])


@unittest.skipUnless(HAS_PIL, "Pillow not installed; render_demo tests skipped")
class TestTerm(unittest.TestCase):
    def make(self, cols=20, rows=3):
        return render_demo.Term(cols, rows)

    def test_ascii_and_colors(self):
        t = self.make()
        t.feed("\x1b[31mR\x1b[0m plain")
        self.assertEqual(row_text(t).rstrip(), "R plain")
        self.assertEqual(t.grid[0][0][1], render_demo.BASE[31])
        self.assertEqual(t.grid[0][0][2], render_demo.DEFAULT_BG)

    def test_bold_and_reset(self):
        t = self.make()
        t.feed("\x1b[1mB\x1b[mN")
        self.assertTrue(t.grid[0][0][3])
        self.assertFalse(t.grid[0][1][3])

    def test_background_color(self):
        t = self.make()
        t.feed("\x1b[44mX")
        self.assertEqual(t.grid[0][0][2], render_demo.BASE_BG[44])

    def test_cr_bs_tab(self):
        t = self.make()
        t.feed("abc\rZ\b\bQ\tT")
        # CR overwrites col 0; backspaces can't go past col 0; tab lands on col 8
        row = row_text(t)
        self.assertEqual(row[0:3], "Qbc")
        self.assertEqual(row[8], "T")

    def test_deferred_autowrap(self):
        t = self.make(5, 2)
        t.feed("abcde")          # fills last column; wrap deferred, row intact
        self.assertEqual(row_text(t, 0).rstrip(), "abcde")
        self.assertEqual(row_text(t, 1).strip(), "")
        t.feed("f")              # forces the wrap first
        self.assertEqual(row_text(t, 0).rstrip(), "abcde")
        self.assertEqual(row_text(t, 1).rstrip(), "f")

    def test_split_csi_across_feeds(self):
        t = self.make()
        t.feed("\x1b[3")
        t.feed("1mR")
        self.assertEqual(row_text(t).rstrip(), "R")
        self.assertEqual(t.grid[0][0][1], render_demo.BASE[31])

    def test_csi_K_erase_line(self):
        t = self.make()
        t.feed("hello\r\x1b[2Kworld")
        self.assertEqual(row_text(t).rstrip(), "world")

    def test_osc_bel(self):
        t = self.make()
        t.feed("\x1b]0;title\aX")
        self.assertEqual(row_text(t).rstrip(), "X")

    def test_osc_st_no_stray_backslash(self):
        # regression: ESC-terminated OSC used to leave the ST backslash on
        # screen, shifting all following text one cell right
        t = self.make()
        t.feed("\x1b]0;window title\x1b\\X")
        self.assertEqual(row_text(t).rstrip(), "X")

    def test_osc_st_followed_by_sgr(self):
        t = self.make()
        t.feed("\x1b]0;t\x1b\\\x1b[31mR\x1b[0m")
        self.assertEqual(row_text(t).rstrip(), "R")
        self.assertEqual(t.grid[0][0][1], render_demo.BASE[31])

    def test_osc_split_across_feeds_st(self):
        t = self.make()
        t.feed("\x1b]0;win")
        t.feed("dow\x1b\\Z")
        self.assertEqual(row_text(t).rstrip(), "Z")

    def test_osc_st_split_across_feeds(self):
        # regression: an ST (ESC \) split at the chunk boundary used to
        # lose the OSC prefix and render the backslash as a stray character
        t = self.make()
        t.feed("\x1b]0;title\x1b")
        t.feed("\\X")
        self.assertEqual(row_text(t).rstrip(), "X")

    def test_osc_st_before_bel_in_same_chunk(self):
        # regression: BEL was searched before ST, so an ST followed by
        # output and a later BEL swallowed everything up to the BEL
        t = self.make()
        t.feed("\x1b]0;t\x1b\\A\x1b]1;x\aB")
        self.assertEqual(row_text(t).rstrip(), "AB")

    def test_osc_truncated_pending(self):
        t = self.make()
        t.feed("\x1b]0;abc")
        self.assertEqual(t.pending, "\x1b]0;abc")
        t.feed("\x1b\\Q")
        self.assertEqual(row_text(t).rstrip(), "Q")
        self.assertEqual(t.pending, "")

    def test_lone_esc_at_chunk_end(self):
        t = self.make()
        t.feed("A\x1b")
        self.assertEqual(t.pending, "\x1b")
        t.feed("[32mG")
        self.assertEqual(row_text(t).rstrip(), "AG")
        self.assertEqual(t.grid[0][1][1], render_demo.BASE[32])


@unittest.skipUnless(HAS_PIL, "Pillow not installed; render_demo tests skipped")
class TestRenderPipeline(unittest.TestCase):
    def _write_cast(self, td, events, width=20, height=5):
        path = os.path.join(td, "t.cast")
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"version": 2, "width": width, "height": height}) + "\n")
            for t, data in events:
                f.write(json.dumps([t, "o", data]) + "\n")
        return path

    def test_render_minimal_cast(self):
        with tempfile.TemporaryDirectory() as td:
            cast = self._write_cast(td, [(0.0, "hi"), (1.0, " there")])
            out = os.path.join(td, "o.gif")
            rc = subprocess.call([sys.executable,
                                  os.path.join(REPO_ROOT, "tools", "render_demo.py"),
                                  cast, out],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.getsize(out) > 0)

    def test_missing_args_usage_exit_2(self):
        # regression: IndexError traceback on missing/insufficient arguments
        for argv_tail in ([], ["only.cast"]):
            with self.subTest(argv_tail=argv_tail):
                p = subprocess.run(
                    [sys.executable,
                     os.path.join(REPO_ROOT, "tools", "render_demo.py")] + argv_tail,
                    capture_output=True, text=True)
                self.assertEqual(p.returncode, 2)
                self.assertIn("usage:", p.stderr)
                self.assertNotIn("Traceback", p.stderr)

    def test_malformed_cast_header(self):
        with tempfile.TemporaryDirectory() as td:
            bad = os.path.join(td, "bad.cast")
            with open(bad, "w", encoding="utf-8") as f:
                f.write("not json\n")
            p = subprocess.run(
                [sys.executable, os.path.join(REPO_ROOT, "tools", "render_demo.py"),
                 bad, os.path.join(td, "o.gif")],
                capture_output=True, text=True)
            self.assertNotEqual(p.returncode, 0)
            self.assertIn("malformed cast header", p.stderr)

    def test_invalid_utf8_cast_clean_error(self):
        # security audit SEC-1: invalid UTF-8 used to die with an uncaught
        # UnicodeDecodeError traceback; it must be a clean error message.
        with tempfile.TemporaryDirectory() as td:
            bad = os.path.join(td, "bad.cast")
            with open(bad, "wb") as f:
                f.write(b'{"version": 2, "width": 40, "height": 10}\n')
                f.write(b'[0.1, "o", "bad \xff\xfe bytes"]\n')
            p = subprocess.run(
                [sys.executable, os.path.join(REPO_ROOT, "tools", "render_demo.py"),
                 bad, os.path.join(td, "o.gif")],
                capture_output=True, text=True)
            self.assertEqual(p.returncode, 1)
            self.assertIn("cannot decode", p.stderr)
            self.assertNotIn("Traceback", p.stderr)

    def test_bad_timestamps_rejected(self):
        # security audit SEC-2: non-numeric / NaN / Infinity timestamps used
        # to crash with a ValueError traceback (at parse or inside render()).
        events = [("string", '["abc", "o", "x"]'), ("nan", '[NaN, "o", "x"]'),
                  ("inf", '[Infinity, "o", "x"]')]
        for name, line in events:
            with self.subTest(timestamp=name):
                with tempfile.TemporaryDirectory() as td:
                    bad = os.path.join(td, "bad.cast")
                    with open(bad, "w", encoding="utf-8") as f:
                        f.write('{"version": 2, "width": 40, "height": 10}\n')
                        f.write(line + "\n")
                    p = subprocess.run(
                        [sys.executable, os.path.join(REPO_ROOT, "tools", "render_demo.py"),
                         bad, os.path.join(td, "o.gif")],
                        capture_output=True, text=True)
                    self.assertEqual(p.returncode, 1, p.stderr)
                    self.assertIn("timestamp", p.stderr)
                    self.assertNotIn("Traceback", p.stderr)

    def test_hostile_cast_headers_rejected(self):
        # security audit round 7: dimensions are the renderer's main
        # memory/CPU amplifier — a 44-byte cast claiming 100000x100000
        # cells never finished pre-fix. Zero/negative/fractional/string/
        # bool/oversized dimensions must be a clean error, never a
        # traceback or a runaway allocation.
        headers = [
            {"version": 2, "width": 0, "height": 0},
            {"version": 2, "width": -5, "height": -3},
            {"version": 2, "width": 40.9, "height": 10.1},
            {"version": 2, "width": "40", "height": "10"},
            {"version": 2, "width": True, "height": True},
            {"version": 2, "width": 100000, "height": 100000},
            {"version": 2, "width": 1000, "height": 101},  # 101_000 cells > cap
        ]
        for hdr in headers:
            with self.subTest(header=hdr):
                with tempfile.TemporaryDirectory() as td:
                    bad = os.path.join(td, "bad.cast")
                    with open(bad, "w", encoding="utf-8") as f:
                        f.write(json.dumps(hdr) + "\n")
                        f.write('[0.1, "o", "x"]\n')
                    p = subprocess.run(
                        [sys.executable, os.path.join(REPO_ROOT, "tools", "render_demo.py"),
                         bad, os.path.join(td, "o.gif")],
                        capture_output=True, text=True, timeout=30)
                    self.assertEqual(p.returncode, 1, p.stderr)
                    self.assertIn("malformed cast header", p.stderr)
                    self.assertNotIn("Traceback", p.stderr)

    def test_non_string_event_data_rejected(self):
        # security audit round 7: non-string event data crashed feed() with
        # a TypeError traceback; it must be a clean error.
        for line in ('[0.1, "o", 123]', '[0.1, "o", null]', '[0.1, "o", [1, 2]]'):
            with self.subTest(line=line):
                with tempfile.TemporaryDirectory() as td:
                    bad = os.path.join(td, "bad.cast")
                    with open(bad, "w", encoding="utf-8") as f:
                        f.write('{"version": 2, "width": 40, "height": 10}\n')
                        f.write(line + "\n")
                    p = subprocess.run(
                        [sys.executable, os.path.join(REPO_ROOT, "tools", "render_demo.py"),
                         bad, os.path.join(td, "o.gif")],
                        capture_output=True, text=True)
                    self.assertEqual(p.returncode, 1, p.stderr)
                    self.assertIn("malformed event data", p.stderr)
                    self.assertNotIn("Traceback", p.stderr)

    def test_huge_final_gap_still_renders(self):
        # security audit round 7: pathological (but finite) gaps must clamp
        # to the GIF 16-bit delay range, not crash int()/Pillow.
        with tempfile.TemporaryDirectory() as td:
            cast = os.path.join(td, "gap.cast")
            with open(cast, "w", encoding="utf-8") as f:
                f.write('{"version": 2, "width": 40, "height": 10}\n')
                f.write('[0.0, "o", "first"]\n[1e15, "o", "last"]\n')
            out = os.path.join(td, "o.gif")
            p = subprocess.run(
                [sys.executable, os.path.join(REPO_ROOT, "tools", "render_demo.py"),
                 cast, out],
                capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertTrue(os.path.getsize(out) > 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
