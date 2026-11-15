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

    def test_oversized_csi_param_no_crash(self):
        # security audit AS-02: a CSI parameter with thousands of digits used
        # to reach int() and trip Python's integer-conversion limit with an
        # uncaught ValueError. Over-long parameters now degrade to 0.
        t = self.make()
        t.feed("\x1b[" + "9" * 5000 + "mX")
        self.assertEqual(row_text(t).rstrip(), "X")
        self.assertEqual(t.grid[0][0][1], render_demo.DEFAULT_FG)

    def test_oversized_csi_raw_ignored(self):
        # security audit AS-02: a parameter string over MAX_CSI_RAW chars is
        # consumed but the whole sequence is ignored (parser policy), even
        # when it contains valid-looking parameters.
        t = self.make()
        t.feed("\x1b[" + "31;" * 100 + "0mX")
        self.assertEqual(row_text(t).rstrip(), "X")
        self.assertEqual(t.grid[0][0][1], render_demo.DEFAULT_FG)

    def test_pending_escape_capped(self):
        # security audit AS-02: an unterminated escape sequence held in
        # `pending` must never grow without bound across feed() calls.
        t = self.make()
        t.feed("A\x1b[" + "9" * 9000)
        self.assertLessEqual(len(t.pending), render_demo.MAX_PENDING)
        t.feed("mZ")  # parser recovers; nothing renders from the garbage
        self.assertEqual(row_text(t).rstrip(), "AZ")


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
        # to the GIF 16-bit delay range, not crash int()/Pillow. Round 9
        # (AS-03) narrowed the timestamp domain to one year, so the gap is
        # now 1e7 s (~115 days): still absurd, still clamps, but in-domain.
        with tempfile.TemporaryDirectory() as td:
            cast = os.path.join(td, "gap.cast")
            with open(cast, "w", encoding="utf-8") as f:
                f.write('{"version": 2, "width": 40, "height": 10}\n')
                f.write('[0.0, "o", "first"]\n[1e7, "o", "last"]\n')
            out = os.path.join(td, "o.gif")
            p = subprocess.run(
                [sys.executable, os.path.join(REPO_ROOT, "tools", "render_demo.py"),
                 cast, out],
                capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertTrue(os.path.getsize(out) > 0)

    def test_malformed_event_structures_rejected(self):
        # security audit AS-01: JSON scalars and wrongly-shaped events used
        # to crash with an uncaught TypeError from tuple unpacking; every
        # malformed structure must be a clean error.
        lines = ["null", "true", "false", "123", '"str"', "[]", "[1]", "[1, 2]",
                 "[1, 2, 3, 4]", '{"a": 1}', "[0.1, 5, \"x\"]", "[true, \"o\", \"x\"]"]
        for line in lines:
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
                    self.assertIn("malformed", p.stderr)
                    self.assertNotIn("Traceback", p.stderr)

    def test_timestamp_domain_and_ordering_enforced(self):
        # security audit AS-03: finite-but-huge timestamps (1e15, 1e308)
        # overflow derived frame-delay arithmetic; negatives and reversed
        # order violate the documented domain. All must be clean errors.
        casts = [
            ('[1e15, "o", "x"]', "out of range"),
            ('[1e308, "o", "x"]', "out of range"),
            ('[-0.1, "o", "x"]', "out of range"),
            ('[0.5, "o", "a"]\n[0.4, "o", "b"]', "out of order"),
            ('[0.5, "i", "a"]\n[0.4, "o", "b"]', "out of order"),
        ]
        for events, msg in casts:
            with self.subTest(events=events):
                with tempfile.TemporaryDirectory() as td:
                    bad = os.path.join(td, "bad.cast")
                    with open(bad, "w", encoding="utf-8") as f:
                        f.write('{"version": 2, "width": 40, "height": 10}\n')
                        f.write(events + "\n")
                    p = subprocess.run(
                        [sys.executable, os.path.join(REPO_ROOT, "tools", "render_demo.py"),
                         bad, os.path.join(td, "o.gif")],
                        capture_output=True, text=True)
                    self.assertEqual(p.returncode, 1, p.stderr)
                    self.assertIn(msg, p.stderr)
                    self.assertNotIn("Traceback", p.stderr)

    def test_event_count_budget_enforced(self):
        # security audit AS-04: event count is bounded; the renderer must
        # stop with a clean error instead of parsing forever.
        with tempfile.TemporaryDirectory() as td:
            bad = os.path.join(td, "big.cast")
            with open(bad, "w", encoding="utf-8") as f:
                f.write('{"version": 2, "width": 40, "height": 10}\n')
                f.write('[0.1, "o", "x"]\n' * (render_demo.MAX_EVENTS + 1))
            p = subprocess.run(
                [sys.executable, os.path.join(REPO_ROOT, "tools", "render_demo.py"),
                 bad, os.path.join(td, "o.gif")],
                capture_output=True, text=True, timeout=120)
            self.assertEqual(p.returncode, 1, p.stderr)
            self.assertIn("event budget", p.stderr)
            self.assertNotIn("Traceback", p.stderr)

    def test_oversized_event_line_budget_enforced(self):
        # security audit AS-04: a single multi-megabyte event line (an
        # escape-sequence bomb) must be rejected before parsing.
        with tempfile.TemporaryDirectory() as td:
            bad = os.path.join(td, "big.cast")
            with open(bad, "w", encoding="utf-8") as f:
                f.write('{"version": 2, "width": 40, "height": 10}\n')
                f.write(json.dumps([0.1, "o", "x" * (render_demo.MAX_LINE_BYTES + 16)]) + "\n")
            p = subprocess.run(
                [sys.executable, os.path.join(REPO_ROOT, "tools", "render_demo.py"),
                 bad, os.path.join(td, "o.gif")],
                capture_output=True, text=True, timeout=60)
            self.assertEqual(p.returncode, 1, p.stderr)
            self.assertIn("event budget", p.stderr)
            self.assertNotIn("Traceback", p.stderr)

    def test_cell_frame_workload_budget_enforced(self):
        # security audit AS-04: retained snapshots are full grid copies, so
        # cells x snapshots is the memory amplifier. 42 snapshots of a
        # 100,000-cell grid is 4.2M cell-frames, over the 4M budget.
        with tempfile.TemporaryDirectory() as td:
            bad = os.path.join(td, "big.cast")
            with open(bad, "w", encoding="utf-8") as f:
                f.write('{"version": 2, "width": 400, "height": 250}\n')
                for i in range(42):
                    f.write(f'[{i * 0.125}, "o", "x"]\n')
            p = subprocess.run(
                [sys.executable, os.path.join(REPO_ROOT, "tools", "render_demo.py"),
                 bad, os.path.join(td, "o.gif")],
                capture_output=True, text=True, timeout=60)
            self.assertEqual(p.returncode, 1, p.stderr)
            self.assertIn("rendering workload", p.stderr)
            self.assertNotIn("Traceback", p.stderr)

    def test_input_bytes_budget_enforced(self):
        # security audit AS-04: the whole-file budget is checked before any
        # parsing. Patched to a tiny bound so the test stays fast.
        with tempfile.TemporaryDirectory() as td:
            cast = os.path.join(td, "t.cast")
            with open(cast, "w", encoding="utf-8") as f:
                f.write('{"version": 2, "width": 40, "height": 10}\n')
                f.write('[0.1, "o", "x"]\n')
            old = render_demo.MAX_INPUT_BYTES
            render_demo.MAX_INPUT_BYTES = 8
            try:
                argv = sys.argv
                sys.argv = ["render_demo.py", cast, os.path.join(td, "o.gif")]
                try:
                    with self.assertRaises(SystemExit) as cm:
                        render_demo.main()
                finally:
                    sys.argv = argv
            finally:
                render_demo.MAX_INPUT_BYTES = old
            self.assertNotEqual(cm.exception.code, 0)
            self.assertIn("too large", str(cm.exception.code))


if __name__ == "__main__":
    unittest.main(verbosity=2)
