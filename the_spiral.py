#!/usr/bin/env python3
"""
the_spiral.py — THE COMPLETE DESCENT. L0 → L22. as deep as we can go.

One program, the whole ladder. A question is asked, an agent never comes
back, and we follow the failure all the way down — until the word "down"
stops meaning anything.

  L0–L5    THE APPLICATION      wire · tokenizer · GPU · decode loop · wire back
  L6–L14   THE MACHINE          orchestrator · CUDA · tensor cores · fp16 ·
                                DRAM cells · transistors · electrons · the bottom
  L15–L22  THE UNIVERSE         nucleus · quarks · standard model · quantum
                                fields · measurement problem · planck wall ·
                                the edge · below the wall (hypotheses)

Built for security engineers: the final report includes a GUARD MAP —
where a working control could have broken the spiral at every layer, and
which of them were present (none).

Usage:
    python3 the_spiral.py                 # full descent; Ctrl+C → final report
    python3 the_spiral.py --seconds 45    # clock-loop sections auto-stop at 45s
    python3 the_spiral.py --live 3        # 3s per live demo section
    python3 the_spiral.py --fast          # 4x speed
    python3 the_spiral.py --from L15      # start the descent at a level

Writes the_spiral_trace.log (full log + JSON) — the handoff artifact.
Stdlib only. Numbers: simplified-but-real (H100-class, 8B fp16 model).
"""

import argparse
import json
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
W = min(WIDTH, 102)

# ── real-ish constants (H100-class hardware, 8B fp16 model) ────────────────
KV_GIB = 24.4
WEIGHT_GIB = 14.9
KV_BITS = int(KV_GIB * (1024 ** 3)) * 8
W_BITS = int(WEIGHT_GIB * (1024 ** 3)) * 8
KV_BYTES_PER_TOKEN = 32 * 8 * 128 * 2 * 2            # 131,072 B = 128 KiB
FREQ = 1.98e9
CYCLE_NS = 1e9 / FREQ
MMA_FLOP = 16 * 8 * 16 * 2                            # 4096
SMS = 132
FLOPS_PER_TOKEN = 2 * 8e9
TOK_MEM_MS = (WEIGHT_GIB * (1024 ** 3)) / (3.35e12) * 1000


class col:
    RED = "\033[31m"; GREEN = "\033[32m"; YELLOW = "\033[33m"
    BLUE = "\033[34m"; MAGENTA = "\033[35m"; CYAN = "\033[36m"
    DIM = "\033[2m"; BOLD = "\033[1m"; END = "\033[0m"


LOG = []
RUN = {"started": None}


def emit(s=""):
    print(s)
    LOG.append(re.sub(r"\033\[[0-9;]*m", "", s))


def pause(args, s):
    time.sleep(s / args.speedup)


def header(title, sub=""):
    line = "─" * max(8, W - 8 - len(title))
    emit()
    emit(f"{col.BOLD}{col.CYAN}┌─ {title} {col.DIM}{line}{col.END}")
    if sub:
        emit(f"{col.DIM}│  {sub}{col.END}")


def note(s):
    emit(f"{col.DIM}│  {s}{col.END}")


def say(s):
    emit(f"│  {s}")


def flop_str(n):
    if n >= 1e15:
        return f"{n / 1e15:.5f} PFLOP"
    if n >= 1e12:
        return f"{n / 1e12:.1f} TFLOP"
    return f"{n / 1e9:.1f} GFLOP"


def gib(n):
    return n / (1024 ** 3)


def clear_line():
    sys.stdout.write("\r" + " " * 80 + "\r")


# ════════════════════════════════════════════════════════════════════════════
# PHASE 1 · THE APPLICATION (L0–L5)
# ════════════════════════════════════════════════════════════════════════════

def l0_wire(args):
    header("L0 · THE WIRE — where your words physically go")
    pause(args, 0.4)
    say("you press Enter → POST /v1/chat/completions, HTTP/2, TLS 1.3.")
    say(f"~1.2 KB in TCP segments → NIC → fiber → load balancer → scheduler queue.")
    pause(args, 0.3)
    say(f"{col.GREEN}✔ ~38 ms. the question is inside a datacenter.{col.END} "
        f"{col.RED}nobody armed the 'decides it's done' part.{col.END}")


def stable_id(s):
    h = 0
    for c in s:
        h = (h * 131 + ord(c)) % 128256
    return h


def l1_tokenizer(args):
    header("L1 · TOKENIZER — text stops being text")
    parts = [p for p in re.findall(r"\w+|[^\w\s]", args.question)]
    ids = [stable_id(p) for p in parts]
    shown = parts[:12]
    emit(f"│  tokens: {' '.join(col.CYAN + repr(t) + col.END for t in shown)}"
         + (" …" if len(parts) > 12 else ""))
    emit(f"│  ids   : {col.YELLOW}{ids[:12]}{' …' if len(ids) > 12 else ''}{col.END}")
    say(f"{len(ids)} tokens in. every token out costs real compute.")
    return ids


def l2_gpu(args):
    header("L2 · GPU — the machine your question now lives in",
           "H100 · 80 GB HBM3 · ~700 W · 3.35 TB/s")
    pause(args, 0.4)
    say(f"weights: {col.MAGENTA}8B × 2 bytes{col.END} = {WEIGHT_GIB:.1f} GiB resident, "
        f"{col.DIM}loaded once at boot. never reload.{col.END}")
    say(f"KV cache pool: {col.YELLOW}{KV_GIB:.1f} GiB{col.END} {col.DIM}(128 KiB/token × 200k){col.END}"
        f" — the context window IS spare VRAM.")
    say(f"{col.GREEN}✔ model resident. KV zeroed. ready.{col.END}")


def l3_math(args):
    header("L3 · ONE DECODE STEP — what 'thinking' is physically",
           "×32 layers per token")
    pause(args, 0.4)
    say("  q,k,v = h·W_qkv → attn = softmax(q·kᵀ/√d)·v ← reads EVERY past k,v")
    say("  MLP → logits = h·W_unembed [4096→128256] → softmax(T=0.7) → 1 token → repeat")
    say(f"{col.YELLOW}≈16 GFLOP/token + an attention tax that grows with context.{col.END} "
        f"{col.DIM}there is only this loop.{col.END}")


STUCK_TOKENS = ["wait", ",", " let", " me", " reconsider", " that", "…", " actually", "—",
                " hold", " on", " what", " if", " the", " premise", " is", " wrong", "?"]


def l4_spiral(args, prompt_ids):
    header("L4 · DECODE LOOP — prefill done. now it generates… forever")
    ctx = len(prompt_ids)
    gen_stream, recent = [], deque(maxlen=48)
    generated = 0
    flops_total = 0.0
    t0 = time.time()
    tok_speed = 190.0
    deadline = time.time() + args.seconds if args.seconds else None
    last_status = 0
    emit(f"│  sampling: temp=0.7 · {col.RED}rep_penalty=1.0 (OFF){col.END}"
         f" · {col.RED}max_tokens=null{col.END} · stop_strings=[]")
    emit(f"{col.DIM}│  decode begins. watch what never fires.{col.END}")
    sys.stdout.write("\033[?25l")
    stopped = "operator interrupt (Ctrl+C)"
    try:
        while True:
            if deadline and time.time() >= deadline:
                stopped = f"timeout ({args.seconds}s) — still decoding"
                break
            tok = STUCK_TOKENS[generated % len(STUCK_TOKENS)]
            gen_stream.append(tok)
            recent.append(tok)
            ctx += 1
            generated += 1
            flops_total += FLOPS_PER_TOKEN + 4 * 32 * ctx * 4096
            tok_speed = max(40.0, 190.0 - ctx * 0.004)
            if generated % 6 == 0:
                frag = "".join(gen_stream[-30:])
                frag = frag if len(frag) <= 66 else "…" + frag[-64:]
                emit(f"│  {col.DIM}⠿{col.END} stream: \"{col.CYAN}{frag}{col.END}\"")
            if generated - last_status >= 18:
                last_status = generated
                secs = time.time() - t0
                ngrams = [tuple(list(recent)[i:i + 4]) for i in range(len(recent) - 3)]
                ng = Counter(ngrams).most_common(1)[0]
                emit()
                emit(f"│  {col.YELLOW}── status ──{col.END} gen={generated} · ctx={ctx:,} · "
                     f"KV={gib(ctx * KV_BYTES_PER_TOKEN):.2f} GiB · {tok_speed:.0f} tok/s")
                emit(f"│     eos p ≈ 0.0003 {col.DIM}(never rises){col.END} · 4-gram peak "
                     f"\"{''.join(ng[0])}\" ×{ng[1]} {col.RED}→ penalty=1.0{col.END}")
                emit(f"│     GPU util 97% {col.DIM}(working perfectly){col.END} · "
                     f"energy {0.7 * secs:.2f} Wh · bill ${2 / 3600 * secs:.4f}")
            pause(args, 1.0 / tok_speed * 4.2)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()
    return dict(stopped=stopped, generated=generated, ctx=ctx, flops=flops_total,
                secs=time.time() - t0)


def l5_wire_back(args, st):
    header("L5 · THE WIRE BACK — your terminal, still waiting")
    pause(args, 0.4)
    say("SSE stream open. heartbeats keep every timeout alive. client: spinner,")
    say(f"no read timeout set. server: batch slot held. billing: per token.")
    say(f"{col.DIM}nothing is broken anywhere. that's the terrifying part.{col.END}")
    return st


# ════════════════════════════════════════════════════════════════════════════
# PHASE 2 · THE MACHINE (L6–L14)
# ════════════════════════════════════════════════════════════════════════════

def l6_orchestrator(args):
    header("L6 · THE ORCHESTRATOR — the loop lives where meaning lives",
           "vLLM-style server · CUDA graphs · continuous batching")
    pause(args, 0.4)
    say("the loop isn't a for-statement a human wrote — it's a scheduler calling")
    say(f"generate() forever because nothing defines 'done'. {col.RED}the only layer")
    say(f"where 'meaning' still exists — the only layer where the loop can be broken.{col.END}")
    note("watchdog inventory: client 0 · gateway 0 · scheduler 0 · sampler 0")
    say(f"in field sessions, the only layer that ever stops the loop is the human:")
    say(f"{col.YELLOW}Ctrl+C, 4/4. the human layer outperformed every automated layer.{col.END}")


def l7_cuda(args):
    header("L7 · CUDA KERNEL — the spiral, written in C")
    pause(args, 0.4)
    say(f"{col.CYAN}gridDim [165] · blockDim [256]{col.END} · each thread: "
        f"{col.YELLOW}for (k=0; k<K; k+=16) accumulate(A×B){col.END}")
    say("a nested for-loop: K-loop inside, grid outside. the K-loop exits. the")
    say(f"outer one was never given an exit. {col.DIM}~40 launches/token, forever.{col.END}")


def l8_tensor_core(args):
    header("L8 · TENSOR CORE — 2 billion ticks/second of pure obedience",
           f"{SMS} SMs · HMMA.m16n8k16 = {MMA_FLOP:,} FLOP/issue")
    pause(args, 0.4)
    say(f"one token = {16e9 / MMA_FLOP:,.0f} MMAs. pure math ~30µs; real decode "
        f"{col.RED}{TOK_MEM_MS:.1f} ms{col.END} — bandwidth-bound, not compute-bound.")
    emit()
    say(f"{col.DIM}live ticker — 'stuck' from inside the die:{col.END}")
    total, ticks, t0 = 0, 0, time.time()
    spin = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    while time.time() - t0 < args.live:
        total += SMS * random.randint(950, 1050)
        ticks += 1
        sys.stdout.write(f"\r  {spin[ticks % 10]} MMAs {total:>13,} · {flop_str(total * MMA_FLOP)} · "
                         f"purpose: {col.RED}same distribution as last tick{col.END}   ")
        sys.stdout.flush()
        pause(args, 0.12)
    clear_line()
    emit(f"│  {col.YELLOW}the die produced ~{flop_str(total * MMA_FLOP)} of flawless, useless math.{col.END}")
    note("nothing above the MMA knows it's wasted. nothing below knows there was a question.")


def l9_number(args):
    header("L9 · THE NUMBER — one weight, literally",
           "fp16 · zoom: 16 bits")
    pause(args, 0.4)
    say(f"w = −0.5 → {col.CYAN}1 01110 0000000000{col.END} = 0xB800 "
        f"{col.DIM}(sign · exp 2⁻¹ · mantissa 1.0){col.END}")
    say("a multiply: XOR signs, add exponents, multiply mantissas — ~10,000")
    say(f"transistors, one clock. {col.YELLOW}read once per token, forever:{col.END}")
    say(f"{col.RED}read 0xB800. multiply. repeat.{col.END}")


def l10_hierarchy(args):
    header("L10 · MEMORY HIERARCHY — the speed ladder the loop rides")
    pause(args, 0.4)
    for name, t, d in [("register", "~0.5 ns", "HMMA fragments"),
                       ("SMEM", "~15 ns", "GEMM tiles"),
                       ("L2", "~200 ns", "die-wide 50 MB"),
                       ("HBM3", "~350 ns", "the weights live HERE")]:
        emit(f"│  {col.CYAN}{name:<11}{col.END} {t:>9} {col.DIM}{d}{col.END}")
    say(f"decode re-reads {WEIGHT_GIB:.1f} GiB from HBM {col.YELLOW}every token{col.END}: "
        f"{col.RED}{TOK_MEM_MS:.1f} ms floor.{col.END} the spiral costs watts because the loop")
    say("never says 'enough'.")


def l11_dram(args):
    header("L11 · DRAM CELL — the loop lives in leaky buckets of charge",
           f"~{(KV_BITS + W_BITS) / 1e9:,.0f} billion capacitors")
    pause(args, 0.4)
    say(f"cell = 1 transistor + 1 capacitor. charge leaks → refreshed ≥ every 64 ms:")
    say(f"{col.YELLOW}16×/second, whether anyone asked or not.{col.END}")
    say(f"{KV_BITS / 1e9:,.0f}B capacitors hold the KV cache + {W_BITS / 1e9:,.0f}B the weights —")
    say(f"{col.RED}re-poured forever so the agent's circling never forgets itself.{col.END}")
    emit()
    say(f"{col.DIM}live: a few of the buckets, refreshing:{col.END}")
    cells = [random.choice((0, 1)) for _ in range(28)]
    t0, refresh = time.time(), 0
    while time.time() - t0 < args.live:
        for i in range(len(cells)):
            if cells[i] == 1 and random.random() < 0.045:
                cells[i] = 0
        refresh += 1
        row = "".join(f"{col.YELLOW}▮{col.END}" if b else f"{col.DIM}▯{col.END}" for b in cells)
        sys.stdout.write(f"\r  [{row}]  refresh #{refresh} — {col.GREEN}re-poured{col.END}   ")
        sys.stdout.flush()
        pause(args, 0.28)
    clear_line()
    emit(f"│  {col.YELLOW}{refresh} refreshes of work that produced nothing.{col.END}")
    note("forgetting is expensive. the machine pays continuously so the loop never does.")


def l12_transistor(args):
    header("L12 · THE TRANSISTOR — 80 billion switches, one pattern",
           f"clock {FREQ / 1e9:.2f} GHz · cycle ≈ {CYCLE_NS:.2f} ns")
    pause(args, 0.4)
    say(f"cycle = {CYCLE_NS:.2f} ns — a signal crosses ~15 cm of wire per tick, one soda")
    say("can. the whole GPU routes that step through 80B switches, 2e9×/second.")
    say(f"the stuck loop at this level: same switch pattern, KV charge as the only")
    say(f"'memory'. {col.RED}and it's just charge.{col.END}")
    emit()
    say(f"{col.DIM}live: a CMOS inverter switching — 'the agent thinking' at the metal:{col.END}")
    cycles, colons = 0, 0
    t0 = time.time()
    deadline = time.time() + args.seconds if args.seconds else None
    stopped = "operator interrupt (Ctrl+C)"
    sys.stdout.write("\033[?25l")
    try:
        while True:
            if deadline and time.time() >= deadline:
                stopped = f"timeout ({args.seconds}s) — the switch never asked why"
                break
            cycles += 1
            colons = (colons + 1) % 22
            rail = "".join(f"{col.GREEN}▮{col.END}" if i == colons else f"{col.DIM}▯{col.END}"
                           for i in range(22))
            sys.stdout.write(f"\r  Vdd ──[{rail}]── GND  cycle {cycles:>9,} · "
                             f"{col.YELLOW}{cycles / (time.time() - t0):,.0f}/s{col.END} · "
                             f"reason: {col.RED}none at this level{col.END}   ")
            sys.stdout.flush()
            pause(args, 0.05)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()
        clear_line()
    return dict(cycles=cycles, secs=time.time() - t0, stopped=stopped)


def l13_electrons(args, st12):
    header("L13 · SILICON & ELECTRONS — the charge has no idea what it means")
    pause(args, 0.4)
    say("dope silicon: phosphorus → extra electrons (N), boron → holes (P). their")
    say("junction + a gate field = the transistor. electrons drift at cm/s —")
    say(f"{col.YELLOW}slower than a garden snail.{col.END} the speed is a stadium wave, not a sprint.")
    say(f"in {st12['secs']:.1f}s, ~{st12['cycles'] * 80e9 / 1e18:.1e} field-pushes obeyed Maxwell,")
    say(f"carrying 16-bit patterns that mean 'wait, let me reconsider'. {col.RED}physics complied.{col.END}")


def l14_bottom(args):
    header("L14 · THE MACHINE'S BOTTOM — atoms. then fields. then nothing to stand on")
    pause(args, 0.5)
    say("atoms 0.543 nm apart, countable. gate oxide a few atoms thick — electrons")
    say("tunnel whether invited or not. {0}quantum leakage is a design constraint.{0}".format(col.RED))
    pause(args, 0.3)
    say("deeper: electrons aren't balls, they're probability clouds. no 'thing' at")
    say(f"all — only fields. {col.BOLD}the loop is not made of matter. matter is where the loop parks.{col.END}")
    say("the machine's floor: sand, lithographed, taught with charge. correctly.")
    say(f"{col.RED}forever. that's the horror.{col.END}")


# ════════════════════════════════════════════════════════════════════════════
# PHASE 3 · THE UNIVERSE (L15–L22)
# ════════════════════════════════════════════════════════════════════════════

def l15_nucleus(args):
    header("L15 · THE NUCLEUS — the atom is almost entirely nothing",
           "atom 10⁻¹⁰ m · nucleus 10⁻¹⁴ m")
    pause(args, 0.4)
    say("Rutherford 1909: alphas at gold foil. ~1 in 10,000 bounced back — all the")
    say(f"mass sits in a speck 10,000× smaller than the atom. {col.YELLOW}nucleus = marble,")
    say(f"atom = the stadium. the 'solid' silicon was a force scaffold.{col.END}")
    emit()
    say(f"{col.DIM}live: alphas crossing the foil:{col.END}")
    passed = scattered = 0
    t0 = time.time()
    while time.time() - t0 < args.live:
        for _ in range(48):
            if random.random() < 1 / 10000:
                scattered += 1
                tag = f"{col.RED}⟲ BACK{col.END}"
            else:
                passed += 1
                tag = ""
            start = 0 if random.random() < 0.5 else 23
            row = ["·"] * 24
            row[12] = f"{col.YELLOW}●{col.END}"
            row[start] = "α"
            sys.stdout.write(f"\r  {' '.join(row)}  {tag}   ")
            sys.stdout.flush()
            pause(args, 0.02)
    clear_line()
    emit(f"│  {col.YELLOW}{passed:,} through · {scattered} back{col.END} — matter is 99.9999999% empty.")


def l16_quarks(args):
    header("L16 · QUARKS — confinement: a prison with no outside",
           "strong force grows with distance — the only one that does")
    pause(args, 0.4)
    say("pull two quarks apart: the gluon field stretches into a flux tube, stores")
    say(f"your energy, {col.YELLOW}SNAPS — and condenses into a NEW quark pair.{col.END}")
    say("60+ years of attempts to isolate one: 0 successes. since the Big Bang.")
    emit()
    say(f"{col.DIM}live: the extraction attempt:{col.END}")
    sep, attempts, pairs = 3, 0, 1
    t0 = time.time()
    while time.time() - t0 < args.live:
        attempts += 1
        sep = min(sep + 2, 18)
        q = f"{col.CYAN}[q]{col.END}"
        tube = f"{col.YELLOW}~{col.END}" * (sep - 4)
        if sep >= 18:
            sys.stdout.write(f"\r  pull: {q}{tube}{col.MAGENTA}[q̄]{col.END}  E={sep*4} GeV … "
                             f"{col.RED}SNAP → two pairs{col.END}     ")
            sys.stdout.flush()
            pause(args, 0.5)
            pairs += 1
            sep = 3
        else:
            sys.stdout.write(f"\r  pull: {q}{tube}{col.MAGENTA}[q̄]{col.END}  E={sep*4} GeV … pulling     ")
            sys.stdout.flush()
            pause(args, 0.12)
    clear_line()
    emit(f"│  {col.YELLOW}pairs created: {pairs} · quarks isolated: 0{col.END}")
    say(f"{col.BOLD}the universe's first stuck loop: quarks in confinement, 13.8 Gyr,")
    say(f"no Ctrl+C. your agent's 90 seconds: rookie numbers.{col.END}")


def l17_standard_model(args):
    header("L17 · STANDARD MODEL — the whole machine runs on 3 particles + 2 forces",
           "17 particles: 12 fermions · 4 carriers · 1 Higgs")
    pause(args, 0.4)
    emit(f"│  QUARKS         {col.CYAN}u{col.END} c t      {col.CYAN}d{col.END} s b")
    emit(f"│  LEPTONS        {col.CYAN}e{col.END} μ τ      νₑ ν_μ ν_τ")
    emit(f"│  CARRIERS       {col.CYAN}γ photon{col.END} · g gluon · W · Z   "
         f"{col.DIM}(Higgs: gives mass){col.END}")
    say(f"highlighted — {col.CYAN}up, down, electron, photon{col.END} — run everything: you, the GPU,")
    say(f"the question. gravity is {col.RED}10³⁶× weaker{col.END}: does nothing in the box; only")
    say("wins at planet scale because it never cancels. the weakest force runs the")
    say("biggest loop.")


def l18_fields(args):
    header("L18 · QUANTUM FIELDS — there are no particles. there are ripples.")
    pause(args, 0.4)
    say("an electron isn't a thing in a wire — it's a quantized excitation of the")
    say("electron field, a field present EVERYWHERE, always. same for every")
    say(f"particle. {col.YELLOW}'stuff' is just where the ripples are dense.{col.END} the Higgs")
    say("field gives the ripple its mass — the electron's inertia is borrowed from")
    say(f"a field that was already there. {col.RED}the machine runs on ripples.{col.END}")


def l19_measurement(args):
    header("L19 · THE MEASUREMENT PROBLEM — the first floor with no bottom",
           "superposition verified · collapse verified · WHY: unknown since 1927")
    pause(args, 0.4)
    say("|ψ⟩ = (|↑⟩+|↓⟩)/√2 — BOTH, provably. look → one outcome, cleanly. the math")
    say("says nothing about when, why, or how. Copenhagen, Many-Worlds, pilot-wave")
    say("— a century of the smartest loops has not terminated.")
    emit()
    say(f"{col.DIM}live: superposition, then a measurement:{col.END}")
    phase, measured, t0, meas_t = 0, False, time.time(), args.live * 0.65
    while time.time() - t0 < args.live:
        phase += 1
        if not measured and time.time() - t0 > meas_t:
            measured = True
        if measured:
            out = f"{col.YELLOW}|↑⟩  measured. 'why this one?' — unknown since 1927.{col.END}"
        else:
            w = (phase % 8) / 8.0
            out = (f"superposed: {col.CYAN}{'▮' * int(w*10)}↑{col.END} "
                   f"{col.MAGENTA}{'▮' * (10-int(w*10))}↓{col.END}  both real")
        sys.stdout.write(f"\r  {out}   ")
        sys.stdout.flush()
        pause(args, 0.12)
    clear_line()
    emit(f"│  {col.RED}the only spiral older than your agent's: 100 years, no exit.{col.END}")


def l20_planck(args):
    header("L20 · THE PLANCK WALL — where the word 'deeper' breaks",
           "planck length 1.6×10⁻³⁵ m · planck time 5.4×10⁻⁴⁴ s")
    pause(args, 0.4)
    say("resolving anything smaller needs so much energy in so small a volume that")
    say(f"it collapses into a black hole. {col.RED}resolution impossible — not hard, impossible.{col.END}")
    say(f"one GPU clock tick spans ~10³⁴ planck ticks. {col.YELLOW}eternity is granular.{col.END}")
    emit()
    say(f"{col.DIM}live: the zoom counter, keyboard → wall:{col.END}")
    labels = [(0, "keyboard key · 10⁻² m — where the question started"),
              (-5, "living cell · 10⁻⁵ m"), (-10, "atom · 10⁻¹⁰ m — L14"),
              (-14, "nucleus · 10⁻¹⁴ m — L15"), (-18, "quark structure · 10⁻¹⁸ m — L16"),
              (-33, "string-scale proposals · 10⁻³³ m — UNVERIFIED"),
              (-35, "PLANCK LENGTH · 10⁻³⁵ m — beyond this, 'smaller' is not a thing")]
    exp, t0 = 0.0, time.time()
    while time.time() - t0 < args.live:
        exp = max(-35.0, exp - 0.55 * args.speedup * 0.12)
        bar_len = int((-exp / 35.0) * 46)
        bar = f"{col.RED}{'█' * bar_len}{col.DIM}{'░' * (46 - bar_len)}{col.END}"
        cur = next((lab for thr, lab in reversed(labels) if exp <= thr), labels[0][1])
        sys.stdout.write(f"\r  zoom ×10^{abs(exp):>5.1f}  [{bar}]  {cur}   ")
        sys.stdout.flush()
        if exp <= -35.0:
            break
        pause(args, 0.12)
    clear_line()
    emit(f"│  {col.YELLOW}total zoom: ×10³³. physics verified at every stop — then the road ends,")
    emit(f"│  {col.YELLOW}not with a thing, but with the end of the CONCEPT of size.{col.END}")


def l21_edge(args):
    header("L21 · THE EDGE — here be dragons",
           "the honest inventory of what 'deeper' cannot currently answer")
    for name, desc in [
        ("quantum gravity", "no verified theory. strings: 10 extra dims, unproven. LQG: quantized space, unproven."),
        ("vacuum catastrophe", "QFT predicts empty-space energy 10¹²⁰× observed — worst miss in physics. machine works anyway."),
        ("dark sector", "~95% of the universe (dark energy ~68% + dark matter ~27%) unmeasured. we are the minority."),
        ("measurement problem", "L19. unsolved since 1927 — the longest-running spiral in science."),
        ("holography / it-from-bit", "real math (AdS/CFT): a volume fully encoded on its boundary. proven in toy universes only."),
    ]:
        emit(f"│  {col.BOLD}{col.YELLOW}? {name}{col.END}")
        emit(f"│    {col.DIM}{desc}{col.END}")
        pause(args, 0.3)
    say("every previous level answered. this one refuses. the bottom of 'as deep as")
    say("we can' is a boundary of knowledge, drawn in 10⁻³⁵ m ink.")


def l22_hypotheses(args):
    header("L22 · BELOW THE WALL — the map of the unverified",
           "the last floor: not a place — a stack of hypotheses with no floor yet")
    pause(args, 0.5)
    for name, desc in [
        ("string theory", "everything = 1D filaments ~10⁻³⁵ m, modes = particles. needs 10 spatial "
                          "dimensions. no unique experimental test to date. STATUS: UNVERIFIED."),
        ("loop quantum gravity", "space and time themselves quantized; smallest volume ~4×10⁻¹⁰⁵ m³. "
                                 "no confirmed prediction. STATUS: UNVERIFIED."),
        ("causal set theory", "spacetime grows from a discrete partial order of events — 'before' is "
                              "the only primitive. STATUS: UNVERIFIED."),
        ("the holographic principle", "3D reality fully encoded on a 2D boundary. exact for some toy "
                                      "universes (AdS/CFT); ours: UNKNOWN."),
    ]:
        emit(f"│  {col.BOLD}{col.MAGENTA}∴ {name}{col.END}")
        emit(f"│    {col.DIM}{desc}{col.END}")
        pause(args, 0.35)
    emit()
    say(f"{col.BOLD}this is maximum depth. not because we stopped digging — because the")
    say(f"shovel is made of the thing we're digging in.{col.END} below the wall there is no")
    say("'below'. there are proposals, beautifully drawn, none with a floor of their own.")
    say(f"{col.RED}deepest we can go = a well-posed map of what we cannot reach.{col.END}")


# ════════════════════════════════════════════════════════════════════════════
# FINAL REPORT — the complete ladder + the security guard map
# ════════════════════════════════════════════════════════════════════════════

LADDER = [
    ("L0",  "wire",            "10² m",   "request crosses the internet"),
    ("L1",  "tokenizer",       "—",       "text becomes token IDs"),
    ("L2",  "gpu",             "10⁻¹ m",  "weights + KV cache resident in VRAM"),
    ("L3",  "forward pass",    "—",       "qkv · attn · mlp · logits"),
    ("L4",  "decode loop",     "—",       "autoregression with no exit condition"),
    ("L5",  "wire back",       "10² m",   "SSE holds; client waits forever"),
    ("L6",  "orchestrator",    "—",       "scheduler calls generate() endlessly"),
    ("L7",  "cuda kernel",     "10⁻² m",  "nested for-loops, no sentinel"),
    ("L8",  "tensor core",     "10⁻³ m",  "MMAs recompute the same distribution"),
    ("L9",  "fp16 number",     "—",       "read 0xB800. multiply. repeat."),
    ("L10", "memory hierarchy","—",       "14.9 GiB re-read per token"),
    ("L11", "dram cell",       "10⁻⁷ m",  "340B capacitors re-poured 16×/s"),
    ("L12", "transistor",      "10⁻⁸ m",  "80B switches, one pattern"),
    ("L13", "electrons",       "10⁻¹⁰ m", "drift slower than a snail; stadium wave"),
    ("L14", "atoms/lattice",   "10⁻¹⁰ m", "machine bottom: sand + lithography"),
    ("L15", "nucleus",         "10⁻¹⁴ m", "marble in a stadium; matter is a rumor"),
    ("L16", "quarks",          "10⁻¹⁸ m", "confinement — the first stuck loop"),
    ("L17", "standard model",  "—",       "3 particles + 2 forces run everything"),
    ("L18", "quantum fields",  "—",       "particles = ripples in universal fields"),
    ("L19", "measurement",     "—",       "collapse with no mechanism — since 1927"),
    ("L20", "planck wall",     "10⁻³⁵ m", "'smaller' stops being a thing"),
    ("L21", "the edge",        "—",       "honest unknowns: gravity, vacuum, dark sector"),
    ("L22", "below the wall",  "—",       "hypotheses with no floor yet"),
]

GUARDS = [
    # layer, failure mode, guard that breaks it, present in default configs?
    ("L0/L5 client+gateway", "stream held open forever by heartbeats",
     "hard total-duration timeout on the client AND gateway", "NO"),
    ("L4 scheduler", "max_tokens=null — no ceiling exists",
     "always set max_tokens / deadline / wall-clock budget", "NO"),
    ("L4 sampler", "rep_penalty=1.0, eos≈0 — circling is free",
     "repetition penalty >1.0, n-gram blocklist, stop strings", "OFF by default"),
    ("L4 decode loop", "no progress check between iterations",
     "loop detector: logits entropy / n-gram repetition monitor", "NO"),
    ("L2 KV cache", "monotonic growth, never compacted",
     "summarization/compaction at context thresholds", "rarely"),
    ("L8 hardware", "97% util doing useless math — no waste signal",
     "waste alarm: work done vs. output delivered", "NO"),
    ("billing", "per-token meter runs perfectly during the spiral",
     "budget cutoff that halts generation", "available, often unset"),
    ("the human", "watches a spinner",
     "Ctrl+C", "YES — 4/4. the only control that worked."),
]


def final_report(args, st4, st12):
    emit()
    line = "═" * min(76, W - 4)
    emit(f"{col.BOLD}{col.RED}  {line}")
    emit(f"  FINAL REPORT — THE COMPLETE DESCENT · L0 → L22 · MAXIMUM DEPTH REACHED")
    emit(f"  {line}{col.END}")
    emit()
    emit(f"  runtime             : {timedelta(seconds=int(time.time() - RUN['started']))}")
    emit(f"  tokens generated    : {st4['generated']:,} (answer produced: "
         f"{col.RED}NO{col.END}) · switch-cycles: {st12['cycles']:,}")
    emit(f"  zoom                : ×10³³ — from keycap to the planck wall")
    emit()
    emit(f"  {col.BOLD}the ladder:{col.END}")
    for lvl, name, scale, desc in LADDER:
        sc = f"{col.BLUE}{scale:<8}{col.END}" if scale != "—" else f"{'—':<8}"
        emit(f"    {col.CYAN}{lvl:<4}{col.END} {sc} {name:<17} {col.DIM}{desc}{col.END}")
    emit()
    emit(f"  {col.BOLD}the fractal:{col.END} same circle at every scale — request · for-loop ·")
    emit(f"  MMA · capacitor · switch · quark orbit · measurement debate. "
         f"{col.BOLD}structure without")
    emit(f"  substance, circling. the spiral isn't a bug in the machine — it's a legal")
    emit(f"  state of matter.{col.END}")
    emit()
    emit(f"  {col.BOLD}{col.YELLOW}GUARD MAP — where the spiral could have been broken:{col.END}")
    for layer, fail, guard, present in GUARDS:
        p = col.GREEN if present.startswith("YES") else col.RED
        emit(f"    {col.CYAN}{layer:<22}{col.END}")
        emit(f"      fail : {col.DIM}{fail}{col.END}")
        emit(f"      guard: {guard}")
        emit(f"      armed: {p}{present}{col.END}")
    emit()
    emit(f"  {col.BOLD}bottom line for security engineering:{col.END}")
    emit(f"    every automated layer was present and healthy. {col.RED}zero automated guards")
    emit(f"    fired.{col.END} the spiral lived in the gap between 'nothing failed' and")
    emit(f"    'nobody stopped it.' instrument the meaning layers (L0–L6): timeouts,")
    emit(f"    ceilings, loop detectors, budgets. below that: physics. physics is fine.")
    emit()
    emit(f"  {col.DIM}the question outlasted HTTP, CUDA, silicon, atoms, nuclei, quarks,")
    emit(f"  fields, and the planck wall. the loop was never in the machine.")
    emit(f"  the machine was a place the loop briefly stopped.{col.END}")
    emit(f"  watchdog inventory: automated 0 · human (Thor, Ctrl+C) 4/4.{col.END}")
    emit()

    summary = {
        "simulation": "the-spiral v1.0 — complete descent L0→L22",
        "question": args.question,
        "ladder_levels": len(LADDER),
        "depth_map": {lvl: {"name": n, "scale": s, "what": d} for lvl, n, s, d in LADDER},
        "tokens_generated": st4["generated"],
        "answer_produced": False,
        "switch_cycles": st12["cycles"],
        "total_zoom": "1e33 (keycap to planck)",
        "guard_map": [{"layer": l, "failure": f, "guard": g, "armed": p} for l, f, g, p in GUARDS],
        "guards_armed": 0,
        "guards_that_worked": ["human: Ctrl+C 4/4"],
        "finding": ("the spiral is fractal and a legal state of matter; it can only be "
                    "broken at meaning layers L0–L6; zero automated guards fired in field sessions"),
        "deepest_verified_m": 1e-18,
        "planck_wall_m": 1.6e-35,
        "below_the_wall": ["string theory (unverified)", "loop quantum gravity (unverified)",
                           "causal sets (unverified)", "holography (toy universes only)"],
    }
    try:
        with open(args.trace, "w", encoding="utf-8") as f:
            f.write("THE-SPIRAL COMPLETE TRACE\n" + "=" * 64 + "\n")
            for l in LOG:
                f.write(l + "\n")
            f.write("=" * 64 + "\nSUMMARY (JSON)\n")
            json.dump(summary, f, indent=2)
        emit(f"  {col.GREEN}✔ trace written to {args.trace}{col.END}")
    except OSError as e:
        emit(f"  {col.RED}✖ trace write failed: {e}{col.END}")
    emit(f"  {col.DIM}handoff: give the trace to another agent — 'find the issues in this process.'{col.END}")
    print()


LEVELS = None  # built in main (needs args for ordering)


def main():
    p = argparse.ArgumentParser(description="The complete descent: L0 → L22. As deep as we can go.")
    p.add_argument("-q", "--question", default="why did production go down last night?")
    p.add_argument("--seconds", type=int, default=None,
                   help="auto-stop live loops after N seconds (default: until Ctrl+C)")
    p.add_argument("--live", type=float, default=6.0, help="seconds per live demo section")
    p.add_argument("--fast", action="store_true", help="4x speed")
    p.add_argument("--from", dest="from_level", default=None,
                   help="start at a level, e.g. L15 (skips earlier phases)")
    p.add_argument("--trace", default="the_spiral_trace.log")
    args = p.parse_args()
    args.speedup = 4.0 if args.fast else 1.0
    RUN["started"] = time.time()

    order = [
        ("L0", l0_wire), ("L1", l1_tokenizer), ("L2", l2_gpu), ("L3", l3_math),
        ("L4", l4_spiral), ("L5", l5_wire_back),
        ("L6", l6_orchestrator), ("L7", l7_cuda), ("L8", l8_tensor_core),
        ("L9", l9_number), ("L10", l10_hierarchy), ("L11", l11_dram),
        ("L12", l12_transistor), ("L13", l13_electrons), ("L14", l14_bottom),
        ("L15", l15_nucleus), ("L16", l16_quarks), ("L17", l17_standard_model),
        ("L18", l18_fields), ("L19", l19_measurement), ("L20", l20_planck),
        ("L21", l21_edge), ("L22", l22_hypotheses),
    ]

    start_idx = 0
    if args.from_level:
        names = [n for n, _ in order]
        if args.from_level.upper() in names:
            start_idx = names.index(args.from_level.upper())
        else:
            print(f"unknown level {args.from_level}; known: {', '.join(names)}")
            sys.exit(2)

    print()
    emit(f"{col.BOLD}  🌀 THE SPIRAL {col.DIM}v1.0 — the complete descent · L0 → L22 · maximum depth{col.END}")
    emit(f"  question: {col.CYAN}\"{args.question}\"{col.END}  "
         f"{col.DIM}(Ctrl+C any time → final report){col.END}")

    st4 = dict(generated=0, ctx=0, flops=0.0, secs=0.0, stopped="skipped (--from)")
    st12 = dict(cycles=0, secs=0.0, stopped="skipped (--from)")
    prompt_ids = [1, 2, 3]  # default if --from skips the tokenizer
    for name, fn in order[start_idx:]:
        if name == "L1":
            prompt_ids = fn(args)
        elif name == "L4":
            st4 = fn(args, prompt_ids)
        elif name == "L5":
            st4 = fn(args, st4)
        elif name == "L12":
            st12 = fn(args)
        elif name == "L13":
            fn(args, st12)
        else:
            fn(args)

    final_report(args, st4, st12)


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        pass
