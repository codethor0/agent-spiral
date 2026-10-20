# Stage A — Security Audit Report: agent-spiral

Date: 2026-10-18 · Auditor: Kimi Work (adversarial posture per master audit prompt)
Baseline audited: `main` @ **c7aaeeb** (one CI-only commit ahead of release), release **v1.1.5** → tag `86d8134` → commit `24d19d8` (annotated). Python 3.12.15, macOS arm64, zsh/Terminal.

## A. Executive verdict

Safe to ship as a **creative/educational terminal demo**: yes. Safe as a **security-education tool**: yes, with the version-banner and trace-interruption items below fixed — not because they are exploitable (none of the confirmed items are), but because a security-education artifact should not misstate its own version or leave a handoff trace that can be mistaken for complete when it is not. Residual risk after fixes: low; the renderer cannot inject terminal sequences (it consumes them into a raster grid), the simulation sanitizes user text, and no secrets exist in history.

**Headline negative result:** the expected OSC 52 / OSC 8 passthrough does **not** exist. The renderer consumes every OSC (BEL- or ST-terminated) without emitting anything to any terminal; the GIF path is inert by construction.

## B. Baseline

- Repo: `codethor0/agent-spiral` · main `c7aaeeb12501139c1cc9e7dab5f3c375b1d1b7c0`
- Release: v1.1.5 (published, not draft) · tag `86d8134` → `24d19d8`; release target `main`
- Diff tag→main: 1 commit (`c7aaeeb`, adds health-check workflow only)
- Tools: `gh` (repos, rulesets, check-runs, releases), python subprocess batteries, `strings`, git history grep across all refs

## C. Confirmed findings

| ID | Sev | Component | File:line | Observed | Root cause | Status |
|---|---|---|---|---|---|---|
| SEC-1 | P3 | renderer input | `tools/render_demo.py:262` | Invalid-UTF-8 cast → uncaught `UnicodeDecodeError` traceback, exit 1 (44/45 fuzz "crashes" are this one bug) | `open(...).read()` decodes without error handling | fix in Stage B |
| SEC-2 | P3 | renderer input | `tools/render_demo.py:283,288` | Timestamp `"abc"` → `ValueError` traceback; `Infinity` timestamp → `ValueError` in `render()` (`int(nan*1000)`) | `float(t)` unvalidated; Python `json` accepts `NaN`/`Infinity` | fix in Stage B |
| SEC-3 | P3 | release integrity | all 5 scripts (see below) | Every banner/trace field says **v1.1.4** while the shipped release is **v1.1.5** | banners hardcoded at 1.1.4, not bumped for release | fix in Stage B (rides next tag — owner decision) |
| SEC-4 | P3 | repudiation | `the_spiral.py:837` (trace open), no SIGTERM/SIGHUP handler | SIGTERM/SIGHUP mid-run → process dies (rc −15/−1), trace left **partial with no truncation marker**, indistinguishable from a complete handoff | incremental spool; only SIGINT is handled (and handled well: trace finished, rc 0) | fix in Stage B |
| SEC-5 | P3 | supply chain | `.github/workflows/*.yml` | Floating action tags (`actions/checkout@v4`, `actions/setup-python@v5`); `pip install pillow` unpinned | no pinning policy | fix in Stage B |
| SEC-6 | P3 | supply chain | `.github/workflows/tests.yml` | No `permissions:` block → GITHUB_TOKEN gets repo default (unset ⇒ permissive) | least-privilege not declared | fix in Stage B |
| SEC-7 | P3 | path handling | `the_spiral.py:837` | `--trace` follows symlinks and overwrites the target (reproduced: symlink → victim file truncated and overwritten); absolute paths accepted | plain `open(path,"w")` | **design decision — options presented, no code change** |

Banner drift locations: `the_spiral.py:720,845` · `stuck_agent.py:155,261` · `agent_stack_spiral.py:346,424` · `deeper_than_this.py:404,482` · `deepest.py:418,479`.

## D. Potential risks (not reproduced / accepted)

- **Cast files played in a real terminal** (asciinema/termtosvg play) would execute any sequences inside — but the repo ships no player, records its own casts, and the rendered artifact is a raster GIF. Not a vulnerability of this project; noted so no one mistakes "renderer is safe" for "casts are sanitized".
- **`--trace` TOCTOU race** (swap symlink between check and open): requires local same-user attacker; not addressed (see SEC-7 options).
- **C1 controls (U+009B/U+009D)** pass through `safe_text` (kept as printable): modern UTF-8 terminals do not interpret them as CSI/OSC; theoretical on legacy ISO-2022 configurations. Hardening only.
- **Renderer GIF output path / font path** accept arbitrary paths: same-user CLI arguments, documented features; no change.
- **Concurrent `--trace` to same path**: last open truncates (standard `open("w")` semantics); user error, POSIX-standard; no shared temp files exist.

## E. Threat-model coverage (STRIDE)

- **Spoofing**: cast/trace forgery examined — no integrity mechanism exists or is claimed (trace is a handoff artifact, not evidence; acceptable, documented in report). Terminal-output spoofing via user text: blocked by `safe_text` (the_spiral.py:73) + `repr()` in tokenizer (the_spiral.py:151); verified.
- **Tampering**: SEC-7 (symlink/absolute trace path) confirmed; atomicity of trace documented as incremental-by-design with SIGINT completion (SEC-4 covers the gap).
- **Repudiation**: SEC-4. Termination-cause reporting verified on all paths: normal rc 0; `--seconds` expiry rc 0 with `demo_control_that_ended_this_run: operator deadline`; SIGINT ×1 rc 0 (trace completed); SIGINT ×2 rc 0 (trace write aborted); invalid args rc 2 (all 12 cases incl. `nan`/`inf`/`-1`/`1e309`); broken pipe rc 1 quiet; renderer missing args rc 2 with usage.
- **Info disclosure**: §G — clean.
- **DoS**: §H fuzzing — no hangs; memory bounded (35.8 MB child RSS over full corpus incl. 5 MB OSC payload; 1 MB OSC in 0.05 s); unbounded `--seconds` rejected by `positive_int`; `--live` rejects non-finite.
- **EoP/code execution**: no `eval`/`exec`/`pickle`/`subprocess(shell=True)`/`os.system` anywhere in runtime code (grepped); CI runs no untrusted PR code with secrets (no `pull_request_target` anywhere).

## F. Supply chain and release integrity

- Workflows: 2 active (`tests`, `ci-health`). No `pull_request_target`, no `${{ github.event.* }}` interpolated into `run:` (health-check passes `run_id` via `env:` — correct pattern), all jobs have `timeout-minutes: 10`, matrix executes renderer tests with Pillow installed (skips = 0 verified in logs earlier; 53/53 per job on latest runs).
- SEC-5/SEC-6 confirmed. Concurrency group absent — acceptable (no shared artifacts).
- Release: annotated tag v1.1.5 resolves to the squash-merge commit; release target matches; CHANGELOG matches the actual diff; demo.cast/sample-trace regenerated from released code and frame-verified in prior round. Release has no assets/checksums (source-only — acceptable, noted). **Tag protection ruleset does not exist** (protect-main covers the branch only) — recommendation, owner decision.
- Repo default workflow permission is unset (⇒ permissive) — recommendation to set read-only.

## G. Secrets and privacy

- History-wide grep (all refs) for key/token/secret/private-key patterns: **no hits**. URLs: shields.io badges only. `/Users/` paths in history: **none**. Hostnames (`Lords-MacBook`) in any committed cast or the GIF: **none** (0 hits at v1.1.4 and current). Env dumps in traces: none (trace records simulation text + JSON summary; question embedded raw inside JSON is properly escaped by `json.dumps`).
- Authors: `codethor0 <codethor@gmail.com>`, `Thor <thor@localhost>`, noreply GitHub address — personal email is visible in git history (public repo; informational, cannot be undone without history rewrite — not recommended).
- Tools/limits: git grep over `git rev-list --all`, `strings` on GIF. Not a scanner like gitleaks — pattern coverage is mine.

## H. Test-suite security value

Existing coverage verified present and specific: termination-cause tests (timeout + Ctrl+C), Planck-claim source scan, sample-trace schema drift test, guard-map field-session labeling, renderer OSC/ST/autowrap/CLI tests (18), numerics recomputation (11). Gaps now closed in Stage B: malformed-input handling (SEC-1/2), banner-vs-changelog consistency check, SIGTERM truncation marker. Suite passes 53/53, 0 skips; what it cannot catch: logic bugs in simulation narration, visual regressions (only spot-checked by frame tests), and any terminal-specific behavior outside the renderer's model.

## I. Claim-integrity findings

- SEC-3 (version banners) — the only *current* overstatement: the tool displays and records "v1.1.4" while being distributed as v1.1.5.
- Prior-round claim fixes re-verified: guard map label, `demo_control_that_ended_this_run`, qualified Planck wording (`test_no_absolute_planck_claims_in_source` passes), sample trace schema test, README Accuracy section present (modeled vs. measured labeled; figures are presented as a model of an H100-class GPU, not measurements).

## J–L. Stage B summary, recommendations, verification

See the draft PR: branch `security/audit-2026-10-18`, fixes SEC-1..SEC-6 with regression tests; SEC-7 and tag protection are **owner decisions** (options in PR body). `main`, tags, and releases untouched; draft PR only.
