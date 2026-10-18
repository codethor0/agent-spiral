#!/usr/bin/env python3
"""
test_simulations.py — stdlib-only test suite for agent-spiral.

Run:
    python3 -m unittest discover -s tests -v
    # or
    python3 tests/test_simulations.py

Covers: compile/import sanity, full fast runs with --seconds, trace JSON
validity, exit codes (bad args, broken pipe), Ctrl+C reporting, and the
terminal-live sections reached via tiny --live values.

TestKnownBugs holds regression tests for defects fixed in v1.1.4 (the
Planck-zoom animation reaching the wall inside the live window).
"""

import json
import os
import py_compile
import signal
import subprocess
import sys
import tempfile
import time
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SIMS = [
    "stuck_agent.py",
    "agent_stack_spiral.py",
    "deeper_than_this.py",
    "deepest.py",
    "the_spiral.py",
]


def run_script(script, extra_args, timeout=120, cwd=None):
    """Run a simulation script; return (returncode, combined_output)."""
    env = dict(os.environ, TERM="dumb", COLUMNS="96", LINES="30")
    return subprocess.run(
        [sys.executable, os.path.join(REPO_ROOT, script)] + extra_args,
        capture_output=True, text=True, timeout=timeout,
        cwd=cwd or REPO_ROOT, env=env,
    )


def extract_summary_json(trace_path, marker="SUMMARY (JSON)"):
    """Parse the machine-readable JSON block from a trace file."""
    with open(trace_path, encoding="utf-8") as f:
        text = f.read()
    assert marker in text, f"trace has no {marker!r} block: {trace_path}"
    payload = text.split(marker, 1)[1].strip()
    # stuck_agent writes post-report chatter after the JSON; decode raw_decode
    dec = json.JSONDecoder()
    obj, _ = dec.raw_decode(payload)
    return obj


class TestCompile(unittest.TestCase):
    def test_all_scripts_compile(self):
        for script in SIMS + [os.path.join("tools", "render_demo.py")]:
            with self.subTest(script=script):
                py_compile.compile(os.path.join(REPO_ROOT, script), doraise=True)


class TestFastRuns(unittest.TestCase):
    """Every script must complete a fast, bounded run with exit 0."""

    def test_stuck_agent_seconds(self):
        with tempfile.TemporaryDirectory() as td:
            r = run_script("stuck_agent.py", ["--fast", "--seconds", "1",
                                              "--trace", os.path.join(td, "t.log")])
            self.assertEqual(r.returncode, 0, r.stderr[-500:])
            d = extract_summary_json(os.path.join(td, "t.log"),
                                     marker="PATHOLOGY SUMMARY (JSON)")
            self.assertIn(d["stopped_by"], ("timeout (1s) — agent was still thinking",))
            self.assertGreater(d["thoughts"], 0)

    def test_stack_spiral_seconds(self):
        with tempfile.TemporaryDirectory() as td:
            trace = os.path.join(td, "t.log")
            r = run_script("agent_stack_spiral.py", ["--fast", "--seconds", "1",
                                                     "--trace", trace])
            self.assertEqual(r.returncode, 0, r.stderr[-500:])
            d = extract_summary_json(trace)
            self.assertTrue(d["stopped_by"].startswith("timeout"))
            self.assertGreater(d["tokens_generated"], 0)
            self.assertGreater(d["kv_cache_gib"], 0)

    def test_deeper_seconds(self):
        with tempfile.TemporaryDirectory() as td:
            trace = os.path.join(td, "t.log")
            r = run_script("deeper_than_this.py",
                           ["--fast", "--seconds", "1", "--demo-seconds", "0.5",
                            "--trace", trace])
            self.assertEqual(r.returncode, 0, r.stderr[-500:])
            d = extract_summary_json(trace)
            self.assertGreater(d["clock_loop_cycles"], 0)

    def test_deepest_full_descent(self):
        with tempfile.TemporaryDirectory() as td:
            trace = os.path.join(td, "t.log")
            r = run_script("deepest.py", ["--fast", "--demo-seconds", "0.5",
                                          "--trace", trace])
            self.assertEqual(r.returncode, 0, r.stderr[-500:])
            d = extract_summary_json(trace)
            self.assertEqual(d["stopped_by"], "completed full descent")
            self.assertEqual(d["deepest_verified_m"], 1e-18)

    def test_the_spiral_seconds(self):
        with tempfile.TemporaryDirectory() as td:
            trace = os.path.join(td, "t.log")
            r = run_script("the_spiral.py",
                           ["--fast", "--live", "0.5", "--seconds", "1",
                            "--trace", trace])
            self.assertEqual(r.returncode, 0, r.stderr[-500:])
            d = extract_summary_json(trace)
            self.assertTrue(d["stopped_by"].startswith("timeout"))
            self.assertEqual(d["ladder_levels"], 23)
            self.assertEqual(len(d["depth_map"]), 23)


class TestArgumentValidation(unittest.TestCase):
    def test_seconds_zero_rejected(self):
        r = run_script("the_spiral.py", ["--seconds", "0"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("positive integer", r.stderr)

    def test_seconds_negative_rejected(self):
        r = run_script("stuck_agent.py", ["--seconds", "-5"])
        self.assertEqual(r.returncode, 2)

    def test_seconds_noninteger_rejected(self):
        r = run_script("agent_stack_spiral.py", ["--seconds", "abc"])
        self.assertEqual(r.returncode, 2)

    def test_unknown_from_level_exit_2(self):
        r = run_script("the_spiral.py", ["--from", "L99"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("unknown level", r.stdout)

    def test_from_level_valid_runs(self):
        with tempfile.TemporaryDirectory() as td:
            trace = os.path.join(td, "t.log")
            r = run_script("the_spiral.py",
                           ["--from", "L15", "--live", "0.3",
                            "--trace", trace])
            self.assertEqual(r.returncode, 0, r.stderr[-500:])


class TestExitBehavior(unittest.TestCase):
    def test_broken_pipe_exits_1_quietly(self):
        """`| head` must not produce 'Exception ignored' noise; exit 1."""
        p1 = subprocess.Popen(
            [sys.executable, os.path.join(REPO_ROOT, "the_spiral.py"), "--fast"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=dict(os.environ, TERM="dumb"))
        p2 = subprocess.Popen(["head", "-n", "3"], stdin=p1.stdout,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p1.stdout.close()
        _, err2 = p2.communicate(timeout=30)
        _, err1 = p1.communicate(timeout=30)
        rc1 = p1.returncode
        self.assertEqual(rc1, 1)
        self.assertNotIn(b"Exception ignored", err2 + err1)

    def test_closed_stdout_fails_quiet(self):
        """fd 1 closed before launch: non-zero exit, no traceback."""
        r = subprocess.run(
            ["bash", "-c",
             f"exec 1>&-; {sys.executable} "
             f"{os.path.join(REPO_ROOT, 'the_spiral.py')} --fast"],
            capture_output=True, text=True, timeout=15,
            env=dict(os.environ, TERM="dumb"))
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("Traceback", r.stderr)


class TestCtrlCReport(unittest.TestCase):
    """SIGINT anywhere in the descent must still produce the final report."""

    def _interrupt(self, script, args, sig_after):
        """SIGINT the script, then return (exit code, parsed summary)."""
        with tempfile.TemporaryDirectory() as td:
            trace = os.path.join(td, "trace.log")
            env = dict(os.environ, TERM="dumb")
            p = subprocess.Popen(
                [sys.executable, os.path.join(REPO_ROOT, script)] + args + ["--trace", trace],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
            time.sleep(sig_after)
            p.send_signal(signal.SIGINT)
            try:
                out, _ = p.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                p.kill()
                p.communicate()
                self.fail(f"{script} hung after SIGINT")
            self.assertNotIn("Traceback", out.decode(errors="replace"))
            marker = ("PATHOLOGY SUMMARY (JSON)"
                      if script == "stuck_agent.py" else "SUMMARY (JSON)")
            d = extract_summary_json(trace, marker=marker)
            return p.returncode, d

    def test_spiral_ctrl_c(self):
        rc, d = self._interrupt(
            "the_spiral.py", ["--fast", "--live", "0.5"], 5)
        self.assertEqual(rc, 0)
        self.assertEqual(d["stopped_by"], "operator interrupt (Ctrl+C)")
        self.assertGreater(d["tokens_generated"], 0)

    def test_stack_spiral_ctrl_c(self):
        rc, d = self._interrupt("agent_stack_spiral.py", ["--fast"], 5)
        self.assertEqual(rc, 0)
        self.assertEqual(d["stopped_by"], "operator interrupt (Ctrl+C)")

    def test_stuck_agent_ctrl_c(self):
        rc, d = self._interrupt("stuck_agent.py", ["--fast"], 3)
        self.assertEqual(rc, 0)
        self.assertEqual(d["stopped_by"], "operator interrupt (Ctrl+C)")

    def test_deeper_ctrl_c(self):
        rc, d = self._interrupt("deeper_than_this.py", ["--fast"], 5)
        self.assertEqual(rc, 0)
        self.assertEqual(d["stopped_by"], "operator interrupt (Ctrl+C)")


class TestKnownBugs(unittest.TestCase):
    """Regression tests for bugs fixed in v1.1.4."""

    def test_planck_zoom_reaches_wall_in_live_window(self):
        """l20_planck drives the zoom from elapsed time, so the animation
        must reach 10^35 within the default live window (v1.1.3 and earlier
        stalled around 10^3 — the PLANCK LENGTH label was never shown)."""
        with tempfile.TemporaryDirectory() as td:
            r = run_script("the_spiral.py",
                           ["--from", "L20", "--live", "6", "--trace",
                            os.path.join(td, "zoom.log")], timeout=30)
        zooms = [ln for ln in r.stdout.splitlines() if "zoom ×10^" in ln]
        self.assertTrue(zooms, "no zoom output captured")
        last = zooms[-1]
        exp_val = float(last.split("zoom ×10^")[1].split()[0])
        self.assertGreaterEqual(exp_val, 35.0,
                                f"zoom only reached 10^{exp_val} of 10^35")


if __name__ == "__main__":
    unittest.main(verbosity=2)
