#!/usr/bin/env python3
"""
stuck_agent.py — Terminal simulation of an AI agent that never comes back.

Ever asked an agent a question and watched it spin forever — reasoning in
circles, re-reading its own thoughts, burning tokens, and never answering?
This program recreates that pathology live in your terminal, then prints a
post-mortem report (and a machine-readable trace file) so other agents can
diagnose what went wrong with the process.

Usage:
    python3 stuck_agent.py                      # default question, runs until Ctrl+C
    python3 stuck_agent.py -q "your question"   # custom question
    python3 stuck_agent.py --seconds 45         # auto-stop after 45s, then autopsy
    python3 stuck_agent.py --fast               # 3.5x speed

Outputs:
    - live terminal animation of the agent getting stuck
    - post-mortem report on exit (Ctrl+C or timeout)
    - stuck_agent_trace.log  (full trace + JSON pathology summary for review)

Stdlib only. No dependencies. Python 3.8+.
"""

import argparse
import itertools
import json
import random
import re
import shutil
import sys
import time
from collections import Counter
from datetime import timedelta

try:
    WIDTH = shutil.get_terminal_size((90, 24)).columns
except Exception:
    WIDTH = 90


class col:
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    DIM = "\033[2m"
    BOLD = "\033[1m"
    END = "\033[0m"


SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
CTX_BUDGET = 200_000  # tokens — a typical large context window

BOOT = [
    "agent core ............. ONLINE",
    "memory bus ............. CONNECTED",
    "reasoning module ....... LOADED",
    "safety filters ......... ARMED",
    "termination checks ..... <none defined>",
]

COHERENT = [
    "OK — decompose the question into its parts.",
    "Part one looks straightforward. Gather context first.",
    "Part two depends on an unstated assumption. Flag it.",
    "Do I have enough information to answer yet? …Unclear.",
    "Sketch a response structure, then verify each claim.",
    "Hmm — before I answer, is the premise even right?",
]

LOOP_TEMPLATES = [
    "wait, let me reconsider that",
    "actually — going back to thought #{n}: \"{t}\" …hmm.",
    "that raises another question, though",
    "let me think about this more carefully",
    "re-reading my earlier reasoning…",
    "is that right? let me double-check",
    "hold on — what if the premise itself is wrong?",
    "i should probably reframe the whole problem",
    "ok, quick recap of where i am: still thinking",
    "one more pass through the context, just to be safe",
    "if i approach it from the other side, maybe…",
    "no wait — circle back. same place. again.",
]

HYPOTHESES = [
    "no termination condition: 'done' was never defined, so the loop guard can never fire",
    "self-referential ingestion: the agent re-reads its own output as if it were new input",
    "missing progress check: no comparator verifies iteration N+1 differs from iteration N",
    "monotonic context growth: nothing is summarized or discarded — the window only fills",
    "frozen confidence signal: a metric exists but is disconnected from the actual reasoning state",
    "no interrupt budget: no max-iterations, max-time, or token ceiling is enforced",
]


def norm(s):
    s = re.sub(r"[^a-z ]", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def est_tokens(s):
    return max(4, int(len(s.split()) * 1.3) + random.randint(2, 17))


def bar(pct, width=14):
    filled = int(width * min(100.0, pct) / 100)
    return "█" * filled + "░" * (width - filled)


def run(args):
    width = min(WIDTH, 100)
    trace_lines = []

    def emit(line=""):
        print(line)
        trace_lines.append(re.sub(r"\033\[[0-9;]*m", "", line))

    # ---- boot sequence -----------------------------------------------------
    print()
    print(f"{col.BOLD}  🧠 stuck-agent simulation {col.DIM}v1.1.1{col.END}")
    print(f"  question: {col.CYAN}\"{args.question}\"{col.END}")
    print()
    for line in BOOT:
        time.sleep(0.12 if not args.fast else 0.04)
        if "<none" in line:
            print(f"  {col.DIM}{line.split('.....')[0]}.....{col.END}{col.RED}{line.split('.....')[1]}{col.END}")
        else:
            print(f"  {col.DIM}{line}{col.END}")
        trace_lines.append(line)
    print(f"  {col.DIM}thinking…{col.END}")
    print()

    # ---- main loop ---------------------------------------------------------
    state = {
        "n": 0,
        "tokens": 0,
        "cycle": 0,
        "counter": Counter(),
        "coherent_seen": False,
        "ctx_full_announced": False,
        "t0": time.time(),
        "stopped": "operator interrupt (Ctrl+C)",
    }
    spin = itertools.cycle(SPINNER)  # infinite spinner, constant memory
    next_beat = 10
    deadline = time.time() + args.seconds if args.seconds else None

    sys.stdout.write("\033[?25l")  # hide cursor
    try:
        while True:
            if deadline and time.time() >= deadline:
                state["stopped"] = f"timeout ({args.seconds}s) — agent was still thinking"
                break

            ch = next(spin)
            state["n"] += 1

            if state["n"] <= len(COHERENT):
                text = COHERENT[state["n"] - 1]
            else:
                state["coherent_seen"] = True
                t = random.choice(LOOP_TEMPLATES)
                if "{n}" in t:
                    t = t.format(n=random.randint(1, max(2, state["n"] // 3)),
                                 t="let me think about this more carefully")
                text = t

            state["tokens"] += est_tokens(text)
            state["counter"][norm(text)] += 1
            pct = state["tokens"] / CTX_BUDGET * 100

            emit(f"  {col.DIM}#{state['n']:04d}{col.END} {col.CYAN}{ch}{col.END} {text}")

            # heartbeat: the loop announcing itself
            if state["n"] >= next_beat:
                next_beat += 10
                state["cycle"] += 1
                beat = (f"    {col.YELLOW}⚠ LOOP CYCLE #{state['cycle']} — conclusion identical to "
                        f"cycle #{state['cycle'] - 1} · confidence 0.42 (unchanged) · "
                        f"context {min(100, int(pct))}% [{bar(pct)}]{col.END}")
                emit(beat)
                if state["cycle"] % 3 == 0:
                    emit(f"    {col.DIM}[internal] plan_stack depth=∞ · next_action=RE-EXAMINE · "
                         f"last_new_idea: none recorded{col.END}")
                if pct >= 100 and not state["ctx_full_announced"]:
                    state["ctx_full_announced"] = True
                    emit(f"    {col.RED}✖ context window FULL — agent continues anyway "
                         f"(it does not notice){col.END}")

            time.sleep(args.speed)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\033[?25h")  # restore cursor
        sys.stdout.flush()

    postmortem(state, args, trace_lines, emit)


def postmortem(state, args, trace_lines, emit):
    elapsed = time.time() - state["t0"]
    total = state["n"]
    unique = len(state["counter"])
    rep_rate = (1 - unique / total) * 100 if total else 0
    pct = min(100.0, state["tokens"] / CTX_BUDGET * 100)

    print()
    line = "═" * min(64, WIDTH - 4)
    emit(f"{col.BOLD}{col.RED}  {line}")
    emit(f"  POST-MORTEM — AGENT NEVER RETURNED")
    emit(f"  {line}{col.END}")
    emit()
    emit(f"  question            : \"{args.question}\"")
    emit(f"  stopped by          : {state['stopped']}")
    emit(f"  time elapsed        : {timedelta(seconds=int(elapsed))}")
    emit(f"  thoughts generated  : {total:,}")
    emit(f"  unique thoughts     : {unique}  (repetition rate {rep_rate:.1f}%)")
    emit(f"  tokens consumed     : {state['tokens']:,} / {CTX_BUDGET:,}  (context {pct:.1f}% full)")
    ans = f"{col.RED}NO{col.END}"
    emit(f"  answer produced     : {ans}")
    emit()

    emit(f"  {col.BOLD}top repeated thoughts:{col.END}")
    for phrase, cnt in state["counter"].most_common(5):
        emit(f"     {cnt:>5,}×  \"{phrase}\"")
    emit()

    emit(f"  {col.BOLD}frozen signals:{col.END}")
    emit(f"     confidence : 0.42 → 0.42 → 0.42  (never updated)")
    emit(f"     loop guard : none — no termination condition defined")
    emit(f"     progress   : identical conclusion across {state['cycle']} consecutive cycles")
    emit()

    emit(f"  {col.BOLD}root-cause hypotheses {col.DIM}(hand these to other agents for review):{col.END}")
    for i, h in enumerate(HYPOTHESES, 1):
        emit(f"     {i}. {h}")
    emit()

    # ---- trace file ---------------------------------------------------------
    summary = {
        "simulation": "stuck-agent v1.1.1",
        "question": args.question,
        "stopped_by": state["stopped"],
        "seconds": round(elapsed, 1),
        "thoughts": total,
        "unique_thoughts": unique,
        "repetition_rate_pct": round(rep_rate, 1),
        "tokens_consumed": state["tokens"],
        "context_budget": CTX_BUDGET,
        "context_pct_full": round(pct, 1),
        "answer_produced": False,
        "top_repeats": dict(state["counter"].most_common(10)),
        "root_cause_hypotheses": HYPOTHESES,
    }
    try:
        with open(args.trace, "w", encoding="utf-8") as f:
            f.write("STUCK-AGENT TRACE\n")
            f.write("=" * 60 + "\n")
            for tl in trace_lines:
                f.write(tl + "\n")
            f.write("=" * 60 + "\n")
            f.write("PATHOLOGY SUMMARY (JSON)\n")
            json.dump(summary, f, indent=2)
        emit(f"  {col.GREEN}✔ trace written to {args.trace}{col.END}")
    except OSError as e:
        emit(f"  {col.RED}✖ could not write trace: {e}{col.END}")
        sys.exit(1)
    emit()
    emit(f"  {col.DIM}next step: hand the trace file to another agent and ask it to")
    emit(f"  find the issues in this process.{col.END}")
    print()


def main():
    p = argparse.ArgumentParser(
        description="Simulate an AI agent that never comes back. Ctrl+C for post-mortem.")
    p.add_argument("-q", "--question", default="Should we refactor the auth module before launch?",
                   help="the question the agent will never answer")
    p.add_argument("--seconds", type=int, default=None,
                   help="auto-stop after N seconds and run the post-mortem")
    p.add_argument("--fast", action="store_true", help="3.5x simulation speed")
    p.add_argument("--trace", default="stuck_agent_trace.log", help="trace output path")
    args = p.parse_args()
    if sys.stdout is None:  # fd 1 was closed before launch
        sys.exit(1)
    args.speed = 0.08 if args.fast else 0.28
    try:
        run(args)
    except BrokenPipeError:
        pass
    except OSError:
        # stdout/stderr unavailable (closed fds, detached tty): fail quiet, not loud
        sys.exit(1)


if __name__ == "__main__":
    main()
