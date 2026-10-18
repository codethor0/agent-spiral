# Changelog

## 1.1.4 - 2026-10-18

Third review round, verified by a new automated test suite.

- Fix the L20 Planck-wall zoom animation in the_spiral.py and deepest.py:
  the exponent now tracks elapsed time instead of a fixed per-iteration
  decrement, so the zoom actually reaches 10^-35 m inside the live window
  (previously it needed ~64 s and stalled around 10^3 at the default --live 6;
  the PLANCK LENGTH label and the early break were unreachable). Also removes
  the dead label loop and the always-1.0 (run_for / max(run_for, 1))
  multiplier in deepest.py.
- Remove dead code: unused charge/hi in deeper_than_this.py L12, unused
  attempts counter in the_spiral.py L16, unused ZOOM global in deepest.py,
  unused coherent_seen flag in stuck_agent.py, and a no-op conditional in
  the agent_stack_spiral.py tokenizer.
- Add tests/test_simulations.py: 18 stdlib-only tests covering compile
  sanity, bounded runs of all five scripts, trace JSON validity, argument
  validation exit codes, broken-pipe / closed-stdout behavior, and Ctrl+C
  reporting.
- Re-record tools/demo.cast and re-render docs/demo.gif from the fixed
  simulation; scrub the recording shell notice and prompt. Regenerate
  traces/sample-trace.log at v1.1.4.
- Version bump to v1.1.4 across all banners and trace summaries.

## 1.1.3 - 2026-10-16

Second adversarial review round: 17 findings, all fixed.

- Interrupt policy now covers the whole lifecycle: stuck_agent.py boots and
  runs under a single guard, so Ctrl+C during boot still produces the
  post-mortem; Ctrl+C during a trace summary write retries once instead of
  losing the trace (second Ctrl+C aborts with exit 130).
- Broken pipe / closed stdout now reliably exits 1: every script flushes
  stdout before interpreter shutdown so EPIPE surfaces during the run, not
  as an "Exception ignored" exit 120.
- Duration arguments are validated: --seconds accepts only positive integers
  up to one year; --live / --demo-seconds accept only positive finite floats.
  Nonsense values (0, -1, inf, 10**400) exit 2 with a clear message.
- Question text is sanitized on every banner/payload line (control
  characters shown as \xNN escapes); the raw question stays in the JSON
  summary.
- Bounded memory everywhere: traces are spooled to disk line-by-line
  (the_spiral.py, agent_stack_spiral.py, stuck_agent.py) and decode streams
  are capped deques, so arbitrarily long runs use O(1) RAM.
- stopped_by is correct on late Ctrl+C in agent_stack_spiral.py and
  deeper_than_this.py (outer interrupt can no longer leave a stale
  "timeout" label).
- the_spiral.py L13 field-push count no longer divides by 1e18.
- Ticker cleanup uses ANSI EL (erase line) instead of fixed-width space
  wipes, so narrow terminals no longer show residue.
- Locale hardening: stdout/stderr reconfigured with errors=
  "backslashreplace"; runs under LC_ALL=C no longer crash on box-drawing
  characters.
- tools/render_demo.py rewritten: pending-escape buffering across chunks,
  deferred autowrap, OSC skipping, per-frame durations, color-aware frame
  dedupe, input-event filtering, true final snapshot, clean errors on
  malformed casts. docs/demo.gif re-rendered from a fresh recording;
  traces/sample-trace.log regenerated at v1.1.3.
- Version bump to v1.1.3 across all banners and trace summaries.

## 1.1.2 - 2026-10-16

- Harden stdout handling in all five simulations: running with fd 1 closed
  or lost mid-run now exits 1 silently instead of raising a traceback.
  Found by adversarial pre-release review (closed-stdout edge case).

## 1.1.1 - 2026-10-16

- Fix energy figure in the_spiral.py L4 status line (Wh conversion was
  3.6x high; now 0.7 kW x secs / 3.6, matching agent_stack_spiral.py).
- Fix "~30us pure math" to ~15us at peak (deeper_than_this.py, the_spiral.py).
- Add stopped_by to the_spiral.py and deeper_than_this.py trace summaries.
- All five scripts now exit 1 when the trace file cannot be written.
- stuck_agent.py spinner uses itertools.cycle instead of an ~80 MB string.
- Remove operator personal name from program output, JSON keys, and the
  sample trace; watchdog lines now say "operator".
- Scrub sandbox hostname and path from tools/demo.cast; re-render
  docs/demo.gif from the scrubbed cast.
- Bump version banners and trace simulation strings to v1.1.1.
- Ctrl+C anywhere in the_spiral, deeper_than_this, deepest, and
  agent_stack_spiral now goes to the final report instead of either
  parking in the next live loop (the_spiral) or dying with a traceback
  (the other three). the_spiral's banner promise "Ctrl+C any time ->
  final report" now holds at every level.
- CONTRIBUTING.md: verification protocol steps all bound their runtime
  (--seconds/--demo-seconds); SECURITY.md notes the render_demo.py
  exception to the no-reads rule.

## 1.1.0 - 2026-10-16

- Community infrastructure: CONTRIBUTING.md (with verification protocol),
  CODE_OF_CONDUCT.md, issue and PR templates, .gitignore.
- Recorded demo of the_spiral.py in docs/demo.gif, with tools/ to re-record.
- README: demo section and badges.

## 1.0.0 - 2026-10-16

- Initial release.
- `stuck_agent.py`: behavior-layer simulation with post-mortem and trace.
- `agent_stack_spiral.py`: application-stack simulation (wire to wire).
- `deeper_than_this.py`: hardware descent (CUDA to electrons).
- `deepest.py`: physics descent (nucleus to Planck wall).
- `the_spiral.py`: unified complete descent L0-L22 with security guard map.
- Example trace under `traces/`.
