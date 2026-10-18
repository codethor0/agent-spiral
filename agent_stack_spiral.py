#!/usr/bin/env python3
"""
agent_stack_spiral.py — Full-stack terminal descent into an AI agent that
never comes back.

Not a cartoon of "thoughts." This walks the ACTUAL pipeline, layer by layer,
with real math:

  your keyboard
    → TCP/TLS over the wire
    → API gateway / scheduler queue
    → tokenizer (text → token IDs)
    → GPU: weights resident in VRAM, KV cache allocated
    → transformer forward pass (the matmuls, one decode step)
    → softmax/temperature sampling
    → autoregressive decode loop  ← this is where it spirals
    → detokenizer → SSE stream → your terminal, still waiting

...and shows what "stuck" means at EVERY layer: same HBM reads, KV cache
growing monotonically, eos probability ~0, no repetition penalty, no
max_tokens, no watchdog. The GPU is happy. The meter is running.

Usage:
    python3 agent_stack_spiral.py                 # full descent, Ctrl+C to end
    python3 agent_stack_spiral.py -q "question"   # your own question
    python3 agent_stack_spiral.py --seconds 40    # decode loop runs 40s, then post-mortem
    python3 agent_stack_spiral.py --fast          # 4x speed

Writes stack_spiral_trace.log (machine-readable) for other agents to review.
Stdlib only. Numbers are simplified-but-real (8B-class model, fp16, GQA).
"""

import argparse
import json
import math
import os
import random
import re
import shutil
import sys
import time
from collections import Counter, deque
from datetime import timedelta

try:
    WIDTH = shutil.get_terminal_size((96, 24)).columns
except Exception:
    WIDTH = 96

W = min(WIDTH, 100)


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


TRACE = None  # trace file spooled incrementally; opened in main()


def safe_text(s):
    # neutralize control characters so question text can never emit terminal
    # escapes or break trace layout; printable text (incl. unicode) is kept
    return "".join(ch if 32 <= ord(ch) != 127 else f"\\x{ord(ch):02x}" for ch in s)


def emit(s=""):
    print(s)
    line = re.sub(r"\033\[[0-9;]*m", "", s)
    if TRACE is not None and not TRACE.closed:
        try:
            TRACE.write(line + "\n")
            TRACE.flush()
        except OSError:
            pass  # trace loss must never kill the simulation


def pause(args, s):
    time.sleep(s / args.speedup)


def header(title):
    line = "─" * max(10, W - 6)
    emit()
    emit(f"{col.BOLD}{col.BLUE}┌─ {title} {col.DIM}{line}{col.END}")


# ────────────────────────────────────────────────────────────────────────────
# Layer 0: the wire
# ────────────────────────────────────────────────────────────────────────────
def layer_wire(args):
    header("LAYER 0 · THE WIRE — where your words physically go")
    pause(args, 0.5)
    emit(f"  you press Enter")
    pause(args, 0.3)
    emit(f"  └─► POST /v1/chat/completions  HTTP/2  TLS 1.3  api.example.ai:443")
    pause(args, 0.3)
    emit(f"      payload: {{\"model\": \"agent-1\", \"messages\": [user: \"{safe_text(args.question)[:46]}\"]}}")
    emit(f"      {col.DIM}~1.2 KB chopped into TCP segments → NIC → fiber → load balancer{col.END}")
    pause(args, 0.4)
    emit(f"  load balancer ──► scheduler queue  {col.DIM}[position #2]{col.END}")
    emit(f"  scheduler: batch slot assigned → GPU node 7")
    pause(args, 0.4)
    emit(f"  {col.GREEN}✔ 38 ms round trip. your question is now inside a datacenter.{col.END}")
    emit(f"  {col.DIM}from here on, nothing comes back until the model decides it's done.{col.END}"
         f" {col.RED}nobody armed the 'decides' part.{col.END}")


# ────────────────────────────────────────────────────────────────────────────
# Layer 1: tokenizer
# ────────────────────────────────────────────────────────────────────────────
def stable_id(s):
    h = 0
    for c in s:
        h = (h * 131 + ord(c)) % 128256
    return h


def layer_tokenizer(args):
    header("LAYER 1 · TOKENIZER — text stops being text")
    pause(args, 0.5)
    emit(f"  {col.DIM}BPE: split into subword units. words you recognize become integers a GPU can eat.{col.END}")
    parts = re.findall(r"\w+|[^\w\s]", args.question)
    toks = parts  # whitespace already excluded by the pattern
    ids = [stable_id(t) for t in toks]
    pause(args, 0.4)
    shown = toks[:14]
    emit(f"  tokens: {' '.join(col.CYAN + repr(t) + col.END for t in shown)}" + (" …" if len(toks) > 14 else ""))
    pause(args, 0.4)
    emit(f"  ids   : {col.YELLOW}{ids[:14]}{' …' if len(ids) > 14 else ''}{col.END}")
    emit(f"  {len(ids)} tokens in. every token you generate from here costs real compute.")
    return ids


# ────────────────────────────────────────────────────────────────────────────
# Layer 2: the GPU — weights + KV cache
# ────────────────────────────────────────────────────────────────────────────
# simplified-but-real 8B-class model, fp16, GQA
P = dict(layers=32, d_model=4096, heads=32, kv_heads=8, head_dim=128,
         vocab=128256, params=8e9, gpu_mem=80e9, gpu_watts=700)
KV_BYTES_PER_TOKEN = P["layers"] * P["kv_heads"] * P["head_dim"] * 2 * 2  # k+v × fp16
CTX_MAX = 200_000
FLOPS_PER_TOKEN = 2 * P["params"]  # dense matmul rule: 2 FLOPs per param per token


def gib(n):
    return n / (1024 ** 3)


def layer_gpu(args):
    header("LAYER 2 · GPU — the machine your question now lives in")
    pause(args, 0.5)
    emit(f"  H100 · 80 GB HBM3 · ~700 W · 3.35 TB/s memory bandwidth")
    pause(args, 0.4)
    emit(f"  weights: {col.MAGENTA}{P['params']/1e9:.0f}B params × 2 bytes{col.END} = "
         f"{gib(P['params']*2):.1f} GiB loaded into VRAM {col.DIM}once, at boot. they never reload.{col.END}")
    pause(args, 0.4)
    emit(f"  KV cache pool allocated: {col.YELLOW}{gib(KV_BYTES_PER_TOKEN * CTX_MAX):.1f} GiB{col.END} "
         f"{col.DIM}(128 KiB per token × {CTX_MAX:,} tokens){col.END}")
    emit(f"  {col.DIM}this pool IS the 'context window'. it's not software. it's spare VRAM.{col.END}")
    pause(args, 0.4)
    emit(f"  {col.GREEN}✔ model resident. KV cache zeroed. ready to think.{col.END}")


# ────────────────────────────────────────────────────────────────────────────
# Layer 3: one forward pass — the actual math
# ────────────────────────────────────────────────────────────────────────────
def layer_math(args):
    header("LAYER 3 · ONE DECODE STEP — what 'thinking' is physically")
    pause(args, 0.6)
    emit(f"  {col.DIM}for the LAST token's position, × 32 layers:{col.END}")
    pause(args, 0.35)
    emit(f"    h = x · W_embed                [{1}×{P['d_model']}] lookup")
    emit(f"    q,k,v = h · W_qkv              [{P['d_model']}→{P['d_model']+2*P['kv_heads']*P['head_dim']}]")
    emit(f"    attn = softmax(q·kᵀ/√d) · v    {col.CYAN}← reads EVERY past k,v from the KV cache{col.END}")
    emit(f"    h = h + MLP(h · W_up · W_down) [{P['d_model']}→11008→{P['d_model']}]")
    pause(args, 0.35)
    emit(f"    logits = h · W_unembed         [{P['d_model']}→{P['vocab']}]  raw scores over the whole vocabulary")
    emit(f"    p = softmax(logits / T)        T=0.7 → sample one token → append → repeat")
    pause(args, 0.4)
    emit(f"  {col.YELLOW}≈16 GFLOP per token (weights) + attention tax that grows with context.{col.END}")
    emit(f"  {col.DIM}there is no 'thinking about it' inside the box. there is only this loop.{col.END}")


# ────────────────────────────────────────────────────────────────────────────
# Layer 4: the spiral — live decode loop
# ────────────────────────────────────────────────────────────────────────────
STUCK_TOKENS = ["wait", ",", " let", " me", " reconsider", " that", "…", " actually", "—",
                " hold", " on", " what", " if", " the", " premise", " is", " wrong", "?"]


def layer_spiral(args, prompt_ids):
    header("LAYER 4 · DECODE LOOP — prefill done, now it generates… forever")
    pause(args, 0.5)

    n_prompt = len(prompt_ids)
    ctx = n_prompt
    generated = 0
    tokens_seen = list(prompt_ids)
    recent = deque(maxlen=48)
    gen_stream = deque(maxlen=64)
    rep_counter = Counter()
    flops_total = 0.0
    t0 = time.time()
    tok_speed = 190.0
    deadline = time.time() + args.seconds if args.seconds is not None else None
    budget_usd_per_s = 2.0 / 3600.0  # $2/GPU-hour rental
    spin = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    si = 0
    last_status = 0
    status_every = 18

    emit(f"  prefill: {n_prompt} tokens processed in parallel → KV cache warm")
    emit(f"  sampling config: temp=0.7 · top_p=0.9 · {col.RED}repetition_penalty=1.0 (OFF){col.END}"
         f" · {col.RED}max_tokens=null{col.END} · stop_strings=[]")
    emit(f"  {col.DIM}decode begins. watch what never fires.{col.END}")
    emit()

    sys.stdout.write("\033[?25l")
    stopped = "operator interrupt (Ctrl+C)"
    try:
        while True:
            if deadline and time.time() >= deadline:
                stopped = f"timeout ({args.seconds}s) — model still decoding"
                break

            tok = STUCK_TOKENS[generated % len(STUCK_TOKENS)]
            gen_stream.append(tok)
            recent.append(tok)
            rep_counter[tok] += 1
            ctx += 1
            generated += 1

            flops_tok = FLOPS_PER_TOKEN + 4 * P["layers"] * ctx * P["d_model"]
            flops_total += flops_tok
            tok_speed = max(40.0, 190.0 - ctx * 0.004)

            if generated % 6 == 0:
                frag = "".join(list(gen_stream)[-30:])
                frag = frag if len(frag) <= 70 else "…" + frag[-68:]
                emit(f"  {col.DIM}{spin[si % len(spin)]}{col.END} stream: \"{col.CYAN}{frag}{col.END}\"")

            if generated - last_status >= status_every:
                last_status = generated
                si += 1
                secs = time.time() - t0
                energy_wh = P["gpu_watts"] * secs / 3600.0
                cost = budget_usd_per_s * secs
                ngrams = [tuple(list(recent)[i:i + 4]) for i in range(len(recent) - 3)]
                top_ng = Counter(ngrams).most_common(1)[0]
                ng_text = "".join(top_ng[0])
                emit()
                emit(f"  {col.YELLOW}── status ──{col.END} gen={generated} · ctx={ctx:,} tokens · "
                     f"KV={gib(ctx*KV_BYTES_PER_TOKEN):.2f} GiB · {tok_speed:.0f} tok/s")
                emit(f"     eos probability      : 0.0003  {col.DIM}(stop token never rises){col.END}")
                emit(f"     4-gram repeat peak   : \"{ng_text}\" ×{top_ng[1]}  "
                     f"{col.RED}→ penalty=1.0, nothing done{col.END}")
                emit(f"     GPU util             : 97% {col.GREEN}{col.DIM}(it is working perfectly){col.END}"
                     f" · energy so far: {energy_wh:.2f} Wh · bill: ${cost:.4f}")

            pause(args, 1.0 / tok_speed * 190 / 45)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()

    secs = time.time() - t0
    return dict(stopped=stopped, generated=generated, ctx=ctx, flops=flops_total,
                secs=secs, energy_wh=P["gpu_watts"] * secs / 3600.0,
                cost=2.0 / 3600.0 * secs, rep=rep_counter)


# ────────────────────────────────────────────────────────────────────────────
# Layer 5: the wire back — and the hang
# ────────────────────────────────────────────────────────────────────────────
def layer_wire_back(args, st):
    header("LAYER 5 · THE WIRE BACK — your terminal, still waiting")
    pause(args, 0.5)
    emit(f"  SSE stream open. heartbeat every 15s keeps every timeout alive.")
    emit(f"  client side: spinner rendering. HTTP read timeout: {col.RED}none set{col.END}.")
    emit(f"  server side: connection holds a batch slot. billing: per token.")
    pause(args, 0.4)
    emit(f"  {col.DIM}nothing is broken anywhere. that's the terrifying part."
         f" every layer is doing exactly what it was told.{col.END}")


# ────────────────────────────────────────────────────────────────────────────
# Post-mortem: the whole stack, layer by layer
# ────────────────────────────────────────────────────────────────────────────
POSTMORTEM = [
    ("client / HTTP", "read timeout, user aborts", "timeout=∞ · user watches a spinner",
     "set a hard timeout; surface liveness"),
    ("API gateway", "idle & stream timeouts", "SSE heartbeats reset the idle clock",
     "cap total stream duration"),
    ("scheduler", "max_tokens ceiling", "max_tokens=null → no ceiling exists",
     "always set max_tokens / deadline"),
    ("sampler", "repetition penalty, n-gram block", "rep_penalty=1.0, no blocklist armed",
     "penalty>1.0 or n-gram stop after k repeats"),
    ("decode loop", "eos / stop strings", "eos logit ≈ 0.0003, never sampled",
     "stop strings + loop detector on logits entropy"),
    ("KV cache", "preemption when VRAM full", "monotonic growth, far from limit, never evicted",
     "summarize/compact long generations"),
    ("GPU / hardware", "watchdog", "97% util, happily matmuling for hours",
     "waste alarm on flat-entropy decode"),
    ("billing meter", "—", "runs perfectly. you pay for the spiral.",
     "budget cutoff"),
]


def postmortem(args, st):
    emit()
    line = "═" * min(72, W - 4)
    emit(f"{col.BOLD}{col.RED}  {line}")
    emit(f"  POST-MORTEM — EVERY LAYER DID ITS JOB. THAT'S THE BUG.")
    emit(f"  {line}{col.END}")
    emit()
    emit(f"  ran for            : {timedelta(seconds=int(st['secs']))}")
    emit(f"  tokens generated   : {st['generated']:,} (ctx now {st['ctx']:,} tokens, "
         f"KV {gib(st['ctx']*KV_BYTES_PER_TOKEN):.1f} GiB)")
    emit(f"  compute burned     : {st['flops']/1e12:,.1f} TFLOP")
    wh = st['energy_wh']
    vibe = "barely a flicker" if wh < 5 else ("a phone charge" if wh < 15 else "a laptop charge")
    emit(f"  electricity        : {wh:,.2f} Wh {col.DIM}(~{vibe}){col.END}")
    emit(f"  bill               : ${st['cost']:.4f} and counting")
    emit(f"  distinct tokens    : {len(st['rep'])} of {sum(st['rep'].values())} generated "
         f"{col.DIM}(vocabulary collapse){col.END}")
    emit(f"  answer delivered   : {col.RED}NO{col.END}")
    emit()
    emit(f"  {col.BOLD}layer-by-layer:{col.END}")
    for name, should, did, fix in POSTMORTEM:
        emit(f"    {col.BOLD}{name:<17}{col.END} should: {col.GREEN}{should}{col.END}")
        emit(f"    {'':<17} did   : {col.RED}{did}{col.END}")
        emit(f"    {'':<17} fix   : {col.CYAN}{fix}{col.END}")
    emit()
    emit(f"  {col.DIM}the spiral lives in the gap between 'no layer failed' and 'nobody stopped it'.{col.END}")

    summary = {
        "simulation": "agent-stack-spiral v1.1.4",
        "question": args.question,
        "stopped_by": st["stopped"],
        "seconds": round(st["secs"], 1),
        "tokens_generated": st["generated"],
        "final_context_tokens": st["ctx"],
        "kv_cache_gib": round(gib(st["ctx"] * KV_BYTES_PER_TOKEN), 2),
        "tflop_burned": round(st["flops"] / 1e12, 1),
        "energy_wh": round(st["energy_wh"], 4),
        "cost_usd": round(st["cost"], 5),
        "distinct_output_tokens": len(st["rep"]),
        "postmortem": [{"layer": n, "should": s, "did": d, "fix": f} for n, s, d, f in POSTMORTEM],
    }
    payload = ("=" * 64 + "\nSUMMARY (JSON)\n" + json.dumps(summary, indent=2) + "\n")
    try:
        try:
            TRACE.write(payload)
            TRACE.flush()
        except KeyboardInterrupt:
            # finish the trace anyway; only a second Ctrl+C aborts the write
            try:
                TRACE.write(payload)
                TRACE.flush()
            except KeyboardInterrupt:
                sys.exit(130)
        TRACE.close()
        emit(f"  {col.GREEN}✔ trace written to {args.trace}{col.END}")
    except OSError as e:
        emit(f"  {col.RED}✖ trace write failed: {e}{col.END}")
        sys.exit(1)
    emit(f"  {col.DIM}hand the trace to another agent: 'find the issues in this process.'{col.END}")
    print()


def positive_int(v):
    try:
        n = int(v)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid int value: {v!r}")
    try:
        float(n)
    except OverflowError:
        raise argparse.ArgumentTypeError(f"value too large: {v!r}")
    if n <= 0:
        raise argparse.ArgumentTypeError(f"value must be a positive integer: {v!r}")
    if n > 366 * 24 * 3600:  # > 1 year is nonsense for a demo
        raise argparse.ArgumentTypeError(f"value too large: {v!r}")
    return n


def main():
    p = argparse.ArgumentParser(description="Full-stack visualization of an agent that never comes back.")
    p.add_argument("-q", "--question", default="why did production go down last night?")
    p.add_argument("--seconds", type=positive_int, default=None,
                   help="decode loop runtime before post-mortem")
    p.add_argument("--fast", action="store_true", help="4x speed")
    p.add_argument("--trace", default="stack_spiral_trace.log")
    args = p.parse_args()
    if sys.stdout is None:  # fd 1 was closed before launch
        sys.exit(1)
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(errors="backslashreplace")
            except (OSError, ValueError):
                pass
    args.speedup = 4.0 if args.fast else 1.0

    global TRACE
    try:
        TRACE = open(args.trace, "w", encoding="utf-8", errors="backslashreplace")
    except OSError as e:
        print(f"cannot open trace file {args.trace}: {e}")
        sys.exit(1)
    TRACE.write("AGENT-STACK-SPIRAL TRACE\n" + "=" * 64 + "\n")
    TRACE.flush()

    print()
    emit(f"{col.BOLD}  ⚡ AGENT STACK SPIRAL {col.DIM}v1.1.4 — descent into an agent that never comes back{col.END}")
    emit(f"  question: {col.CYAN}\"{safe_text(args.question)}\"{col.END}")

    st = dict(secs=0.0, generated=0, ctx=0, flops=0.0, energy_wh=0.0, cost=0.0,
              rep=Counter(), stopped="operator interrupt (Ctrl+C)")
    try:
        layer_wire(args)
        ids = layer_tokenizer(args)
        layer_gpu(args)
        layer_math(args)
        st = layer_spiral(args, ids)
        layer_wire_back(args, st)
    except KeyboardInterrupt:
        # any Ctrl+C anywhere still gets the post-mortem, labeled correctly
        st["stopped"] = "operator interrupt (Ctrl+C)"
    postmortem(args, st)


if __name__ == "__main__":
    try:
        main()
        # flush here so a broken pipe surfaces now, not at interpreter
        # shutdown (where it would print "Exception ignored" and exit 120)
        if sys.stdout is not None:
            sys.stdout.flush()
    except BrokenPipeError:
        # stdout went away mid-run (e.g. `| head`): exit quietly, report failure
        try:
            os.dup2(os.open(os.devnull, os.O_WRONLY), 1)
        except OSError:
            pass
        sys.exit(1)
    except OSError:
        # stdout/stderr unavailable (closed fds, detached tty): fail quiet, not loud
        sys.exit(1)
