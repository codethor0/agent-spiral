# Contributing

Thanks for helping. This file is short on purpose; read it before opening a
pull request.

## Ground rules

- The simulations stay standard-library only. No new dependencies. The only
  exception is `tools/render_demo.py`, which needs Pillow to render the demo
  GIF.
- Small, readable, single-purpose functions. No cleverness that needs a
  comment to be safe.
- Documentation is plain ASCII: no em dashes, no marketing tone. Say what it
  does, how, and why.
- No secrets, credentials, personal data, or machine-specific paths in the
  repo, ever.

## Verification protocol (run before every PR)

Every change ships with evidence that the programs still work. Run all of
this from the repo root and paste the results into the PR:

```bash
python3 -m py_compile *.py tools/render_demo.py
python3 stuck_agent.py --fast --seconds 1
python3 agent_stack_spiral.py --fast --seconds 1
python3 deeper_than_this.py --fast --seconds 1
python3 deepest.py --fast --demo-seconds 1
python3 the_spiral.py --fast --live 1 --seconds 1
python3 the_spiral.py --fast --live 1 --from L15 --seconds 1
python3 - <<'EOF'
import json
s = open('the_spiral_trace.log').read()
json.loads(s.rsplit('SUMMARY (JSON)\n', 1)[1])
print('trace JSON ok')
EOF
```

Each run must exit 0 and write its trace file. If a trace file cannot be
written, that is a bug: report it.

## Git workflow

- Branch from main, open a PR, get review, squash merge. No direct pushes
  to main.
- One logical change per commit; commit messages describe the change in
  plain language.
- Note for trace files: many systems have a global gitignore that skips
  `*.log`. The sample trace is named `traces/sample-trace.log` and may need
  `git add -f traces/sample-trace.log` the first time you clone. Runtime
  traces (`*_trace.log`) are ignored on purpose and should not be committed.

## Re-recording the demo

```bash
{ sleep 1; echo "python3 the_spiral.py --fast --live 1 --seconds 1"; \
  sleep 45; echo "exit"; } | python3 -m termtosvg record tools/demo.cast -g 104x30
python3 tools/render_demo.py tools/demo.cast docs/demo.gif
```

Re-record only when program output changes visibly. If you change the
recording, check the GIF for ghost frames before committing: seek through
several frames in an image viewer. (Known trap: quantize frames to a
palette BEFORE saving the multi-frame GIF; passing palette arguments at
save time corrupts Pillow's frame differencing.)

## Ideas backlog

Things we may want, in no particular order:

- A `--json` flag for machine-only output (no ANSI).
- CI matrix over Python 3.8 to 3.13 running the verification protocol.
- A text mode for screen readers (replace live demos with static text).
