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

---

# Round 9 — Zero-Known-Defect Release Gate (2026-10-19)

Auditor: Kimi Work, per the "MASTER PROMPT: AGENT-SPIRAL ZERO-KNOWN-DEFECT RELEASE GATE"
brief. Baseline: `main` @ **629799f** (release **v1.1.6** → tag `96f0d1c`, annotated).
Branch: `audit/round-9`. Suite: **77 tests, 0 skips** (+16 over v1.1.6).

## R9 findings and resolutions

| ID | Severity | Component | Finding | Resolution |
|---|---|---|---|---|
| AS-01 | P3 | renderer input | JSON event scalars (`null`/`true`/`123`/`"str"`) raised an uncaught `TypeError` from tuple unpacking; non-string event codes were silently skipped; wrong-length arrays hit the message for the wrong layer | structure + field-type validation before unpacking; every malformed shape is a clean exit-1 diagnostic |
| AS-02 | P3 | renderer parser | a CSI parameter with >4300 digits reached `int()` and died on Python's conversion limit; an unterminated CSI/OSC could grow `pending` without bound | parser policy: ≤19 digits per parameter (longer degrade to 0), parameter strings >256 chars consumed-but-ignored, `pending` capped at 4096 bytes (ESC+introducer retained so a capped sequence still completes as ignored) |
| AS-03 | P3 | renderer time domain | finite-but-huge timestamps (`1e15`, `1e308`) passed validation but overflowed derived frame-delay arithmetic; negatives and reversed order were silently normalized | documented domain enforced at parse: finite, `0 ≤ t ≤ 1 year`, non-decreasing; `render()` clamps holds to 0.02–600 s before `int()` as defense in depth |
| AS-04 | P3 | renderer resources | the 100k-cell cap alone did not bound the full allocation chain (file bytes, line bytes, event count, snapshot count, retained cells) | explicit budgets: 32 MiB input, 1 MiB/line, 500k events, 20k snapshots, 4M cell-frames (~280 MB worst case; the shipped demo is ~1.3M). Every over-budget cast exits 1 with a clear message |
| AS-05 | P3 | path handling | `--trace` followed symlinks and could overwrite an unrelated target (previously SEC-7, documented only) | `open_trace()`: `O_NOFOLLOW` on the leaf + `fstat` on the opened fd (closes the TOCTOU race) + regular-file requirement; `O_NONBLOCK` so a FIFO open cannot hang the process. Symlink/dangling/fifo/dir refused with clean errors; regular-file behavior unchanged. Symlinked parents still followed (standard resolution) |
| AS-06 | P3 | CI workflow | health-check opened a tracking issue on failure but never closed it on recovery; dedupe matched loosely (`in:title`) | exact-title jq filter on both paths; recovery step (`if: success()`) closes only the exact tracking issue; least-privilege permissions unchanged |
| AS-07 | P3 | documentation | README said 51 tests (suite: 61→77); CONTRIBUTING wishlisted a 3.8–3.13 matrix (actual: 3.11–3.13); security report ended at round 8 | README count → 77 (final count taken from the completed suite); CONTRIBUTING matrix corrected; this section documents round 9 |

## R9 verification

- Every AS-01..AS-05 fix has a reproducer that failed pre-fix and passes post-fix (16 new tests; the round-7 huge-gap test was re-pointed at 1e7 s — inside the new domain, same clamp semantics — rather than weakened).
- Adversarial spot checks (subprocess, no host risk): 5000-digit CSI → clean render; unterminated OSC ×9 KB → `pending` ≤ 4096 and clean recovery; `1e308`/negative/reversed timestamps → exit 1, no traceback; 100k-cell grid × 42 snapshots → "rendering workload" error; symlink/fifo/directory/dangling `--trace` → exit 1, victim file untouched, no hang.
- jq exact-match filter verified against fixtures: only the precisely-titled issue matches; near-miss titles (`(old)`, `— nightly`, body mentions) never close; empty result on a healthy run closes nothing.
- demo.cast re-recorded from the v1.1.7 code (`termtosvg`, same protocol) and docs/demo.gif re-rendered; first/last frames visually verified (banner v1.1.7, complete guard map, no ghosting).
- Version sync: all five simulation scripts + renderer agree on **v1.1.7** (`test_all_scripts_agree_on_version`).

## R9 residual items (owner decisions, unchanged from round 8)

- Tag-protection ruleset for `v*` and read-only default workflow permission: recommended, not applied (repository Settings changes require owner action).
- Cast files played in a real terminal execute their sequences (no player ships with the repo) — documented risk, not a defect.
