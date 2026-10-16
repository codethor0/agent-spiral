# Changelog

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
