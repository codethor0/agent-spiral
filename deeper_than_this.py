#!/usr/bin/env python3
"""
deeper_than_this.py — below the GPU. as deep as physics lets us go.

agent_stack_spiral.py ended at "the GPU runs a loop." this program opens the
GPU and keeps drilling, one abstraction at a time:

  L6   orchestrator (vLLM-style scheduler, CUDA graphs)
  L7   CUDA kernel — grid/block/thread, the GEMM tiles
  L8   SM / tensor core — warp schedulers, MMA instructions, live FLOP ticker
  L9   the number — what a weight literally is (fp16 bit pattern)
  L10  memory hierarchy — register/SMEM/HBM latency ladder
  L11  the DRAM cell — capacitors holding the KV cache, refresh cycles
  L12  the transistor — 80B switches doing the same switch, forever
  L13  silicon & electrons — doped atoms, drift slower than a garden snail
  L14  the bottom — atoms, then fields. there is no "thing" down here.

and the punchline that ties it to the stuck agent: the loop is FRACTAL.
request → token → MMA → switch → charge slosh. same circle at every scale.
the only layer that can break it is the top one.

Usage:
    python3 deeper_than_this.py                 # full descent; final clock loop runs till Ctrl+C
    python3 deeper_than_this.py --seconds 30    # auto-stop the clock loop, then descent report
    python3 deeper_than_this.py --fast          # 4x speed

Writes deeper_trace.log for other agents to review. Stdlib only.
Numbers: H100-class hardware, 8B fp16 model, simplified but real.
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
from datetime import timedelta

try:
    WIDTH = shutil.get_terminal_size((96, 24)).columns
except Exception:
    WIDTH = 96

W = min(WIDTH, 102)

KV_GIB = 24.4
WEIGHT_GIB = 14.9
KV_BITS = int(KV_GIB * (1024 ** 3)) * 8          # ~210 billion bits
W_BITS = int(WEIGHT_GIB * (1024 ** 3)) * 8       # ~128 billion bits
DRAM_CELLS = (KV_BITS + W_BITS) / 1e9            # billions of capacitors
FREQ = 1.98e9                                     # H100 boost clock
CYCLE_NS = 1e9 / FREQ                             # ~0.505 ns
MMA_FLOP = 16 * 8 * 16 * 2                        # HMMA.m16n8k16 = 4096 FLOP
SMS = 132
TFLOPS = 989e12
BW_TB = 3.35                                      # TB/s HBM
TOK_MEM_MS = (WEIGHT_GIB * (1024 ** 3)) / (BW_TB * 1e12) * 1000  # per-token weight re-read


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


LOG = []


def emit(s=""):
    print(s)
    LOG.append(re.sub(r"\033\[[0-9;]*m", "", s))


def pause(args, s):
    time.sleep(s / args.speedup)


def header(title, sub=""):
    line = "─" * max(8, W - 8 - len(title))
    emit()
    emit(f"{col.BOLD}{col.MAGENTA}┌─ {title} {col.DIM}{line}{col.END}")
    if sub:
        emit(f"{col.DIM}│  {sub}{col.END}")


def note(s):
    emit(f"{col.DIM}│  {s}{col.END}")


def say(s):
    emit(f"│  {s}")


# ────────────────────────────────────────────────────────────────────────────
# L6 — the orchestrator
# ────────────────────────────────────────────────────────────────────────────
def l6_orchestrator(args):
    header("L6 · THE ORCHESTRATOR — where the stack spiral handed off the loop",
           "vLLM-style inference server · CUDA graphs · continuous batching")
    pause(args, 0.5)
    say("the decode loop from layer 4 isn't a 'for' statement a human wrote.")
    pause(args, 0.35)
    say("it's a scheduler process that keeps calling generate() because nothing")
    say("in its config says when to stop. the loop lives HERE, at the API layer —")
    say(f"{col.RED}the only layer where 'meaning' still exists.{col.END}")
    pause(args, 0.4)
    note("watchdog inventory so far: client timeouts 0 · gateway 0 · scheduler 0 · sampler 0")
    note("in your real session the only layer that ever stopped the loop was")
    say(f"the human. {col.YELLOW}4 runs. 4 × Ctrl+C. 100% success rate.{col.END} "
        f"the human layer outperformed every automated layer combined.")


# ────────────────────────────────────────────────────────────────────────────
# L7 — CUDA kernel
# ────────────────────────────────────────────────────────────────────────────
def l7_cuda(args):
    header("L7 · CUDA KERNEL — the loop, written in C, launched 1000×/second",
           "one decode step = ~40 kernel launches · launch overhead ~3–5 µs each")
    pause(args, 0.5)
    say("your token becomes a grid of thread blocks:")
    pause(args, 0.35)
    say(f"  {col.CYAN}gridDim  [165, 1, 1]{col.END}   ← blocks across the SMs")
    say(f"  {col.CYAN}blockDim [256, 1, 1]{col.END}  ← threads per block, 8 warps")
    say(f"  each thread: {col.YELLOW}for (k = 0; k < K; k += 16) accumulate(A_frag × B_frag){col.END}")
    pause(args, 0.4)
    note("look at that line. a for-loop accumulating fragments. the spiral is")
    note("literally a nested for-loop now — grid outside, K-loop inside. it")
    say(f"terminates when K is consumed. {col.RED}the outer loop has no such exit.{col.END}")
    pause(args, 0.3)
    say(f"launch ▓▓▓▓▓▓▓▓▓▓ gemm_qkv ✔   launch ▓▓▓▓▓▓▓▓▓▓ attn ✔   launch ▓▓▓▓▓▓▓▓▓▓ mlp ✔")
    say(f"launch ▓▓▓▓▓▓▓▓▓▓ lm_head ✔  …×40   {col.DIM}every token. forever.{col.END}")


# ────────────────────────────────────────────────────────────────────────────
# L8 — SM / tensor core (live MMA ticker)
# ────────────────────────────────────────────────────────────────────────────
def flop_str(n):
    if n >= 1e15:
        return f"{n / 1e15:.5f} PFLOP"
    if n >= 1e12:
        return f"{n / 1e12:.1f} TFLOP"
    return f"{n / 1e9:.1f} GFLOP"


def l8_tensor_core(args):
    header("L8 · SM / TENSOR CORE — 2 billion ticks per second of pure obedience",
           f"H100: {SMS} SMs · 4th-gen tensor cores · ~989 TFLOP/s fp16 dense")
    pause(args, 0.5)
    say("every clock tick, each SM's tensor core can fire one instruction:")
    say(f"  {col.CYAN}HMMA.m16n8k16{col.END} — a 16×8×16 block of multiply-accumulates "
        f"= {col.YELLOW}{MMA_FLOP:,} FLOP{col.END}, in one issue.")
    say(f"  all {SMS} SMs together: ~{SMS * MMA_FLOP * FREQ / 1e15:.2f} PFLOP/s at peak.")
    pause(args, 0.4)
    say(f"one token needs 16 GFLOP ÷ {MMA_FLOP} = {16e9 / MMA_FLOP:,.0f} MMAs. "
        f"pure math: ~15µs. actual decode: ~{TOK_MEM_MS:.1f} ms.")
    say(f"  {col.RED}the GPU is not slow at thinking. it's a memory problem.{col.END} "
        f"(next levels.)")
    emit()
    say(f"{col.DIM}live ticker — this is what 'stuck' looks like from inside the die:{col.END}")
    emit()

    total = 0
    t0 = time.time()
    ticks = 0
    spin = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    run_for = min(args.demo_seconds, 8 if not args.fast else 4)
    while time.time() - t0 < run_for:
        batch = SMS * random.randint(950, 1050)
        total += batch
        ticks += 1
        pf = flop_str(total * MMA_FLOP)
        sys.stdout.write(f"\r  {spin[ticks % 10]} MMAs {total:>13,} · {pf} · "
                         f"purpose: {col.RED}the same token distribution as last tick{col.END}   ")
        sys.stdout.flush()
        pause(args, 0.12)
    sys.stdout.write("\r" + " " * 78 + "\r")
    emit(f"│  {col.YELLOW}in {run_for:.0f}s of watching, the die produced "
         f"~{flop_str(total * MMA_FLOP)} of flawless, useless math.{col.END}")
    pause(args, 0.3)
    note("nothing above the MMA knows it's wasted. nothing below knows there was a question.")


# ────────────────────────────────────────────────────────────────────────────
# L9 — the number
# ────────────────────────────────────────────────────────────────────────────
def l9_number(args):
    header("L9 · THE NUMBER — what a weight literally is",
           "zoom: forget tensors. this is 16 bits.")
    pause(args, 0.5)
    say("take one weight, w = -0.5, stored fp16:")
    pause(args, 0.4)
    say(f"  {col.CYAN}1 01110 0000000000{col.END}   = 0xB800")
    say(f"  {col.DIM}↑ sign   ↑ exp(2⁻¹)   ↑ mantissa(1.0)   →  −(1.0 × 2⁻¹) = −0.5{col.END}")
    pause(args, 0.4)
    say("a multiply is: XOR the signs, add the exponents, multiply the mantissas,")
    say("renormalize. ~10,000 transistors cooperate to do it in one clock.")
    pause(args, 0.35)
    say(f"{col.YELLOW}this one 16-bit pattern will be read from HBM once per generated token{col.END}")
    say(f"until the heat death of the session. 3.9 million of its friends right behind it.")
    say(f"  {col.RED}the loop, at this level, is just: read 0xB800. multiply. repeat.{col.END}")


# ────────────────────────────────────────────────────────────────────────────
# L10 — memory hierarchy
# ────────────────────────────────────────────────────────────────────────────
def l10_hierarchy(args):
    header("L10 · MEMORY HIERARCHY — the speed ladder the loop rides",
           "latency is distance. the loop pays rent at every rung.")
    pause(args, 0.5)
    rows = [
        ("register file",  "~0.5 ns",   "1 cycle",    "where HMMA fragments live"),
        ("SMEM (L1/shared)", "~15 ns",  "~30 cycles", "GEMM tiles staged here"),
        ("L2 cache",       "~200 ns",   "~400 cycles", "die-wide, 50 MB"),
        ("HBM3 (off-die)", "~350 ns",   "~700 cycles", f"3.35 TB/s — the weights live HERE"),
    ]
    for name, t, c, d in rows:
        say(f"  {col.CYAN}{name:<18}{col.END} {t:>8} {col.DIM}{c:>14}{col.END}  {d}")
    pause(args, 0.5)
    say(f"decode reads {WEIGHT_GIB:.1f} GiB of weights from HBM {col.YELLOW}every single token{col.END}:")
    say(f"  {WEIGHT_GIB:.1f} GiB ÷ 3.35 TB/s = {col.RED}{TOK_MEM_MS:.1f} ms/token{col.END} — "
        f"the hard floor. bandwidth-bound, not compute-bound.")
    say(f"  that is why your spiral costs real time and real watts: {col.BOLD}the same 16 GiB,")
    say(f"  re-read, forever, because the loop never says 'enough.'{col.END}")


# ────────────────────────────────────────────────────────────────────────────
# L11 — the DRAM cell (live refresh)
# ────────────────────────────────────────────────────────────────────────────
def l11_dram(args):
    header("L11 · THE DRAM CELL — the loop is stored in leaky buckets of charge",
           f"KV cache + weights = ~{DRAM_CELLS:,.0f} billion capacitors")
    pause(args, 0.5)
    say("an HBM cell: one transistor + one capacitor. charge above threshold = 1.")
    say("the charge LEAKS. every cell must be re-read and re-written — refreshed —")
    say(f"at least every 64 ms. {col.YELLOW}16× per second. whether anyone asked or not.{col.END}")
    pause(args, 0.4)
    say(f"your spiral, physically: {col.CYAN}{KV_BITS/1e9:,.0f} billion capacitors in the KV cache "
        f"+ {W_BITS/1e9:,.0f} billion in the weights,{col.END}")
    say("each one a tiny bucket the machine re-pours 16×/second, forever, to keep")
    say(f"{col.RED}the agent's circling immortal.{col.END}")
    emit()
    say(f"{col.DIM}live: a few of the ~340 billion buckets holding your stuck KV cache{col.END}")
    emit()
    cells = [random.choice((0, 1)) for _ in range(28)]
    t0 = time.time()
    run_for = min(args.demo_seconds, 7 if not args.fast else 3.5)
    refresh = 0
    while time.time() - t0 < run_for:
        # decay: random cells leak toward 0
        for i in range(len(cells)):
            if cells[i] == 1 and random.random() < 0.045:
                cells[i] = 0
        refresh += 1
        row = "".join(f"{col.YELLOW}▮{col.END}" if b else f"{col.DIM}▯{col.END}" for b in cells)
        sys.stdout.write(f"\r  [{row}]  refresh #{refresh} — {col.GREEN}all cells re-poured{col.END}   ")
        sys.stdout.flush()
        pause(args, 0.28)
    sys.stdout.write("\r" + " " * 78 + "\r")
    emit(f"│  {col.YELLOW}in {run_for:.0f}s, the memory did {refresh} refreshes of work that produced nothing.{col.END}")
    pause(args, 0.3)
    note("forgetting is expensive. the machine pays it continuously so the loop never has to.")


# ────────────────────────────────────────────────────────────────────────────
# L12 — the transistor (live clock loop)
# ────────────────────────────────────────────────────────────────────────────
def l12_transistor(args):
    header("L12 · THE TRANSISTOR — 80 billion switches, one pattern",
           f"H100 die · ~80B transistors · clock {FREQ/1e9:.2f} GHz · cycle ≈ {CYCLE_NS:.2f} ns")
    pause(args, 0.5)
    say("a MOSFET: voltage on the gate opens a channel between source and drain.")
    say("no moving parts. a switch made of electric fields in doped silicon.")
    pause(args, 0.4)
    say(f"clock tick = {CYCLE_NS:.2f} ns. in that time a signal moves ~15 cm in wire —")
    say("about one soda can. the entire GPU is a machine that routes that soda-can-")
    say("sized step of charge through 80 billion switches, 2 billion times a second.")
    pause(args, 0.4)
    say(f"{col.YELLOW}the stuck agent's decode loop, at this level:{col.END}")
    say("  the same switch pattern, re-executed, with the KV cache's charge state")
    say(f"  as the only 'memory' that anything ever happened. {col.RED}and it's just charge.{col.END}")

    emit()
    say(f"{col.DIM}live: CMOS inverter, the atom of all of it, switching at clock speed —{col.END}")
    say(f"{col.DIM}this is 'the agent thinking', one level above the metal:{col.END}")
    emit()

    charge = ["·"] * 22
    hi = list(range(0, 22, 4))
    t0 = time.time()
    cycles = 0
    colons = 0
    deadline = time.time() + args.seconds if args.seconds is not None else None
    stopped = "operator interrupt (Ctrl+C)"
    sys.stdout.write("\033[?25l")
    try:
        while True:
            if deadline and time.time() >= deadline:
                stopped = f"timeout ({args.seconds}s) — the switch never asked why"
                break
            cycles += 1
            colons = (colons + 1) % 22
            rail = "".join(f"{col.GREEN}▮{col.END}" if i == colons else f"{col.DIM}▯{col.END}" for i in range(22))
            sys.stdout.write(f"\r  Vdd ──[{rail}]── GND    clock cycle {cycles:>9,} · "
                             f"{col.YELLOW}{cycles / (time.time() - t0):,.0f} switches/s{col.END} · "
                             f"reason: {col.RED}none at this level{col.END}   ")
            sys.stdout.flush()
            pause(args, 0.05)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()
        sys.stdout.write("\r\033[2K")  # EL: erase whole line, any terminal width

    secs = time.time() - t0
    return dict(cycles=cycles, secs=secs, stopped=stopped)


# ────────────────────────────────────────────────────────────────────────────
# L13 — silicon & electrons
# ────────────────────────────────────────────────────────────────────────────
def l13_electrons(args, st):
    header("L13 · SILICON & ELECTRONS — the charge has no idea what it means",
           "5 nm-class process · features a few dozen atoms wide · gate oxide: a few atoms thick")
    pause(args, 0.5)
    say("dope silicon with phosphorus → extra electrons (N-type). dope with boron →")
    say("holes (P-type). put them together → a depletion region → a gate field that")
    say("widens or collapses it. that field IS the transistor. solid-state physics,")
    say("no exceptions granted for AI.")
    pause(args, 0.4)
    say(f"electron drift velocity in these wires: order of cm/s at real current densities —")
    say(f"{col.YELLOW}slower than a garden snail.{col.END} the speed comes not from electrons")
    say("racing, but from 80 billion of them pushing in organized waves — the machine")
    say("is a stadium wave, not a sprint.")
    pause(args, 0.4)
    say(f"in {st['secs']:.1f}s of the switch loop above, ~{st['cycles'] * 80e9 / 1e18:.2f} zillion")
    say("field-pushes happened, obeying Maxwell, carrying the same 16-bit patterns")
    say(f"that encode 'wait, let me reconsider that'. {col.RED}physics complied perfectly.{col.END}")


# ────────────────────────────────────────────────────────────────────────────
# L14 — the bottom
# ────────────────────────────────────────────────────────────────────────────
def l14_bottom(args):
    header("L14 · THE BOTTOM — atoms. then fields. then nothing to stand on",
           "zoom: 10⁻¹⁰ m and falling")
    pause(args, 0.6)
    say("one more level: the silicon lattice — atoms 0.543 nm apart, countable.")
    say("below that: electrons aren't little balls, they're probability clouds —")
    say("and at gate-oxide thicknesses of a few atoms, they tunnel whether we want")
    say("them to or not. {0}quantum leakage is a design constraint now, not a bug.{0}".format(col.RED))
    pause(args, 0.5)
    say("go deeper and there is no 'thing' at all — only fields and amplitudes.")
    say(f"{col.BOLD}the loop is not made of matter. matter is just where the loop parks.{col.END}")
    pause(args, 0.5)
    say("this is the actual bottom of the stack:")
    say(f"  {col.CYAN}sand. arranged by lithography. taught with charge to hold a pattern")
    say(f"  that says the agent is 'thinking'.{col.END} it is. correctly. forever. that's the horror.")


# ────────────────────────────────────────────────────────────────────────────
# Descent report
# ────────────────────────────────────────────────────────────────────────────
def descent_report(args, st):
    emit()
    line = "═" * min(74, W - 4)
    emit(f"{col.BOLD}{col.RED}  {line}")
    emit(f"  DESCENT REPORT — WE WENT AS DEEP AS PHYSICS LETS US")
    emit(f"  {line}{col.END}")
    emit()
    emit(f"  levels descended    : L6 → L14 (below: fields, then 'nobody knows'")
    emit(f"  final clock loop    : {st['cycles']:,} switch-cycles in {st['secs']:.1f}s — "
         f"no question was answered at any point in the descent")
    emit()
    emit(f"  {col.BOLD}the fractal:{col.END}")
    for lvl, view in [
        ("L0–L5", "HTTP request loops between client and datacenter"),
        ("L6",    "scheduler calls generate() with no exit condition"),
        ("L7",    "kernel launches nest for-loops with no sentinel"),
        ("L8",    "MMAs recompute the same distribution forever"),
        ("L11",   "capacitors re-pour the same charge 16×/second"),
        ("L12",   "switches repeat one pattern, 2e9×/second"),
    ]:
        emit(f"    {col.CYAN}{lvl:<7}{col.END} {view}")
    emit(f"  {col.BOLD}same circle, every scale. the spiral isn't a bug in the machine —")
    emit(f"  it's a legal state of matter.{col.END}")
    emit()
    emit(f"  {col.BOLD}where it can be broken:{col.END}")
    emit(f"    only the top layers carry meaning. only there can 'done' be defined.")
    emit(f"    everything below L6 is physics doing what physics does.")
    emit(f"    {col.YELLOW}you cannot debug a capacitor. you can only configure the layer above it.{col.END}")
    emit()
    emit(f"  {col.DIM}and the only watchdog that fired in your real session — 4 for 4 — was you.{col.END}")
    emit()

    summary = {
        "simulation": "deeper-than-this v1.1.3",
        "stopped_by": st["stopped"],
        "levels": ["orchestrator", "cuda_kernel", "tensor_core", "fp16_number",
                   "memory_hierarchy", "dram_cell", "transistor", "silicon_electrons", "bottom_fields"],
        "clock_loop_cycles": st["cycles"],
        "clock_loop_seconds": round(st["secs"], 1),
        "dram_cells_billions": round(DRAM_CELLS, 1),
        "kv_bits_billions": round(KV_BITS / 1e9),
        "weight_bits_billions": round(W_BITS / 1e9),
        "ns_per_clock_cycle": round(CYCLE_NS, 3),
        "flop_per_mma": MMA_FLOP,
        "ms_per_token_floor": round(TOK_MEM_MS, 1),
        "finding": "the loop is fractal; only meaning-layer (<=L6) can break it",
        "watchdog_inventory": {"automated": 0, "human_operator_ctrl_c": 4},
    }
    try:
        with open(args.trace, "w", encoding="utf-8") as f:
            f.write("DEEPER-THAN-THIS TRACE\n" + "=" * 64 + "\n")
            for l in LOG:
                f.write(l + "\n")
            f.write("=" * 64 + "\nSUMMARY (JSON)\n")
            json.dump(summary, f, indent=2)
        emit(f"  {col.GREEN}✔ trace written to {args.trace}{col.END}")
    except OSError as e:
        emit(f"  {col.RED}✖ trace write failed: {e}{col.END}")
        sys.exit(1)
    emit(f"  {col.DIM}hand it to another agent: 'find the issues in this process.'{col.END}")
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


def positive_float(v):
    try:
        x = float(v)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid float value: {v!r}")
    if not math.isfinite(x):
        raise argparse.ArgumentTypeError(f"value must be finite: {v!r}")
    if x <= 0:
        raise argparse.ArgumentTypeError(f"value must be positive: {v!r}")
    return x


def main():
    p = argparse.ArgumentParser(description="Descend below the GPU, as deep as physics allows.")
    p.add_argument("--seconds", type=positive_int, default=None,
                   help="run the final transistor clock loop for N seconds (default: until Ctrl+C)")
    p.add_argument("--demo-seconds", type=positive_float, default=6,
                   help="length of each live demo section")
    p.add_argument("--fast", action="store_true", help="4x speed")
    p.add_argument("--trace", default="deeper_trace.log")
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

    print()
    emit(f"{col.BOLD}  🔻 DEEPER THAN THIS {col.DIM}v1.1.3 — stack_spiral ended at the GPU. that was the foyer.{col.END}")
    emit(f"  {col.DIM}same question riding all the way down: \"why did production go down?\"{col.END}")

    st = dict(cycles=0, secs=0.0, stopped="operator interrupt (Ctrl+C)")
    try:
        l6_orchestrator(args)
        l7_cuda(args)
        l8_tensor_core(args)
        l9_number(args)
        l10_hierarchy(args)
        l11_dram(args)
        st = l12_transistor(args)
        l13_electrons(args, st)
        l14_bottom(args)
    except KeyboardInterrupt:
        # any Ctrl+C anywhere still gets the descent report, labeled correctly
        st["stopped"] = "operator interrupt (Ctrl+C)"
    descent_report(args, st)


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
