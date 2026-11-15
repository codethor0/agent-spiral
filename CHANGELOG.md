# Changelog

## 1.1.7 - 2026-10-19

Security audit round 9 ("zero-known-defect release gate", branch
audit/round-9); every fix has a regression test. 77 tests, 0 skips.

- tools/render_demo.py: every malformed event shape — JSON scalars
  (null/true/numbers/strings), wrong-length arrays, objects, non-string
  event codes — is a clean exit-1 diagnostic instead of an uncaught
  TypeError from tuple unpacking or a silent skip (AS-01).
- tools/render_demo.py: ANSI parser bounds — at most 19 digits per CSI
  parameter, parameter strings over 256 chars consumed-but-ignored, and a
  4096-byte cap on escape sequences pending across feed() chunks (AS-02).
- tools/render_demo.py: documented timestamp domain enforced at parse —
  finite, 0..1 year, non-decreasing; frame-delay arithmetic clamps to
  0.02..600 s before int() (AS-03).
- tools/render_demo.py: explicit resource budgets — 32 MiB input, 1 MiB
  per event line, 500k events, 20k snapshots, 4M cell-frames (AS-04).
- the_spiral.py: --trace refuses symlinks (O_NOFOLLOW), special files
  (fstat on the opened fd), and cannot hang on a FIFO (O_NONBLOCK); a
  symlink can no longer redirect the trace onto an unrelated file (AS-05).
- .github/workflows/health-check.yml: a green daily run closes the exact
  tracking issue; failure dedupe matches the exact title only (AS-06).
- README/CONTRIBUTING/docs synced to the 77-test suite, the 3.11–3.13
  matrix, and the round-9 audit record; banners and the re-recorded
  demo.cast/demo.gif now say v1.1.7 (AS-07).

## 1.1.6 - 2026-10-19

Security audit rounds 7–8 (branch security/audit-2026-10-18), Stage A
read-only review plus surgical fixes; every fix has a regression test.

- tools/render_demo.py: a cast file that is not valid UTF-8 or that carries
  a non-numeric / NaN / Infinity timestamp now exits with a clear message
  instead of an uncaught traceback (security audit SEC-1, SEC-2; found by
  fuzzing the parser with random and adversarial bytes).
- tools/render_demo.py: hostile cast headers are rejected — width/height
  must be true positive integers totaling at most 100,000 cells. A 44-byte
  cast claiming 100000x100000 cells previously never finished (round 7
  resource-exhaustion finding; the grid is allocated per event snapshot).
- tools/render_demo.py: non-string event data is a clean error instead of
  a TypeError traceback, and pathological (but finite) frame gaps are
  clamped to the GIF 16-bit delay range instead of crashing int()/Pillow.
- the_spiral.py: SIGTERM/SIGHUP mid-run previously killed the process and
  left an incremental trace that looked like a complete handoff. The trace
  now gets an explicit "[TRACE INTERRUPTED]" marker and the process exits
  128+signal (security audit SEC-4). SIGINT behavior is unchanged.
- safe_text() (the_spiral.py, stuck_agent.py, agent_stack_spiral.py): now
  neutralizes every Unicode control character — C1 controls, bidi
  overrides (U+202E), zero-width format characters — not just C0, so a
  crafted question can no longer spoof or reorder terminal output or
  poison trace layout. Letters from all real scripts are unaffected
  (round 7 terminal-spoofing finding).
- Version banners and trace "simulation" fields in all five scripts bumped
  to v1.1.6: the released v1.1.5 still displayed v1.1.4 (security audit
  SEC-3). A test now fails if the scripts ever disagree on the version.
- CI hardening: actions pinned to full commit SHAs (checkout v4.3.1,
  setup-python v5.6.0) and tests.yml declares permissions: contents: read
  (security audit SEC-5, SEC-6).
- Support matrix raised to Python 3.11+: 3.8–3.10 are end of life and
  receive no security fixes. This also unblocks the Pillow pin: Pillow
  10.4.0 (the last 3.8-compatible release) has 34 known OSV advisories;
  CI now installs Pillow 13.0.0 (zero known advisories). README badge and
  support statement updated; the protect-main ruleset's required checks
  now match the 3.11/3.12/3.13 matrix.

Decisions left to the owner (see PR body): --trace symlink policy
(guard vs. document), a tag-protection ruleset, and the repo's default
workflow permission (still unset/permissive).

## 1.1.5 - 2026-10-18

Audit rounds 4–6 (branch audit/v1.1.4-full-review), verified by an
expanded automated suite.

- the_spiral.py: the trace summary no longer reports human Ctrl+C
  unconditionally. New fields: simulated_agent_guards_fired (always 0 in
  the simulation), demo_control_that_ended_this_run (Ctrl+C, --seconds
  deadline, or none), and field_session_record (the 4/4 history, clearly
  labeled as such). deeper_than_this.py and deepest.py watchdog fields
  relabeled to field_session_record for the same reason.
- the_spiral.py and deepest.py L20: the Planck-length endpoint frame is
  always displayed, even for very short --live / --demo-seconds windows
  that expire before the animation lands on 10^35.
- Absolute Planck-scale wording qualified in both scripts: the wall is
  presented as the limit of current theory ("with known physics",
  "shortest tick current physics can define"), not a measured limit of
  nature. README Accuracy section states where verified physics ends
  (~10^-18 m) and theory begins. Follow-up: deepest.py L20 header and
  final finding now say distance/duration stop being definable rather
  than stop existing.
- --seconds help text and README now state explicitly that it bounds only
  the L4/L12 live loops, not the whole descent.
- Guard map: the human Ctrl+C entry now reads "YES — 4/4 in field
  sessions; this run's control is reported in the summary", so history
  cannot be confused with the current run's termination.
- traces/sample-trace.log regenerated to match the current JSON schema
  (demo_control_that_ended_this_run, field_session_record); a test now
  fails if the sample trace drifts from the current format again.
- Add 4 regression tests (suite grew to 51 after the round-5 renderer
  tests): endpoint frame on tiny windows, demo_control on timeout and
  Ctrl+C runs, no absolute Planck claims in source.

- Fix tools/render_demo.py: OSC sequences terminated by ST (ESC \) no
  longer leave a stray backslash on screen; missing/insufficient command
  line arguments now print a usage message and exit 2 instead of an
  IndexError traceback. Follow-up: an ST split across feed() chunks is
  reassembled instead of leaking a stray backslash, and when a chunk
  contains both an ST and a later BEL the earliest terminator wins (a
  later BEL can no longer swallow output after the ST).
- the_spiral.py and deepest.py L20: the zoom window now measures elapsed
  time with time.monotonic(), so wall-clock adjustments cannot stall or
  skip the animation; both levels now state the two reference frames
  explicitly (counter counts orders below 1 m; the keycap-to-wall trip is
  x10^33).
- Add tests/test_render_demo.py (18 tests): renderer escape sequences,
  OSC-BEL / OSC-ST termination (including ST split across chunks and
  ST-before-BEL precedence), split sequences, deferred autowrap, CLI
  validation. Skips without Pillow.
- Add tests/test_numerics.py (11 tests): independent recomputation of the
  hardware model (KV bytes per token, weight GiB, KV pool, per-token
  memory floor, MMA FLOP, clock period, DRAM cell counts) plus ladder
  scale ordering.
- Fix stale test-module documentation and give every interrupt test its
  own temporary directory (no shared fixed paths).
- Add .github/workflows/tests.yml: runs the suite on Linux and macOS,
  Python 3.9-3.13, on push and pull request. CI installs Pillow so the
  renderer tests execute instead of skipping; 3.8 added to the matrix to
  match the advertised Python 3.8+ support.
- Suite is now 53 tests; docs/demo.gif re-recorded after the L20 note and
  again after the guard-map wording change, with the final-report frames
  machine-verified against the current output.
- Fix flaky kv_cache_gib assertion in test_stack_spiral_seconds: the
  expected value is recomputed from the reported final_context_tokens
  instead of asserting > 0, so lightly loaded CI runners (where the value
  rounds to 0.00) no longer fail the job.

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
