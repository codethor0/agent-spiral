#!/usr/bin/env python3
"""
deepest.py — below the atom. as deep as physics currently lets us go.

deeper_than_this.py ended at L14: atoms, then fields, "then nobody knows."
this program keeps going — and finds out exactly where "deeper" stops
meaning anything:

  L15  the nucleus — the atom is 99.9999999% empty. matter is a rumor.
  L16  quarks — confinement: a prison with no outside. the FIRST stuck loop.
  L17  the standard model — 3 particles + 2 forces run the entire machine.
  L18  quantum fields — "particles" are ripples. fields fill the universe.
  L19  the measurement problem — superposition, collapse… and an honest
       "we don't know." the first level with no bottom.
  L20  the planck wall — 10^-35 m, where distance itself stops existing.
  L21  the edge — quantum gravity, the vacuum catastrophe, the dark sector.
       here be dragons.
  ∞    the answer to "can we go deeper?": no. and that IS the bottom.

Usage:
    python3 deepest.py                 # full descent (interactive demos ~6s each)
    python3 deepest.py --fast          # 4x speed
    python3 deepest.py --demo-seconds 10

Writes deepest_trace.log. Stdlib only. Numbers real; unknowns marked unknown.
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

try:
    WIDTH = shutil.get_terminal_size((96, 24)).columns
except Exception:
    WIDTH = 96

W = min(WIDTH, 102)


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
    emit(f"{col.BOLD}{col.RED}┌─ {title} {col.DIM}{line}{col.END}")
    if sub:
        emit(f"{col.DIM}│  {sub}{col.END}")


def note(s):
    emit(f"{col.DIM}│  {s}{col.END}")


def say(s):
    emit(f"│  {s}")


ZOOM = {"m": 1.0}  # cumulative zoom tracker (meters scale)


# ────────────────────────────────────────────────────────────────────────────
# L15 — the nucleus
# ────────────────────────────────────────────────────────────────────────────
def l15_nucleus(args):
    header("L15 · THE NUCLEUS — the atom is almost entirely nothing",
           "atom ≈ 10⁻¹⁰ m · nucleus ≈ 10⁻¹⁴ m · the 'solid' lattice from L14 was a force scaffold")
    pause(args, 0.5)
    say("Rutherford, 1909: shoot alpha particles at gold foil.")
    say("if atoms were pudding, all alphas plow through. result: ~1 in 10,000 bounced BACK.")
    say(f"{col.YELLOW}conclusion: all the mass is in a speck 10,000× smaller than the atom.{col.END}")
    pause(args, 0.4)
    say("scale: nucleus = a marble. atom = the stadium around it. the marble is the atom.")
    say("everything else — the 'solid' silicon — is electrons held by fields. empty.")
    emit()
    say(f"{col.DIM}live: alphas crossing the gold foil (marble center, mostly empty):{col.END}")
    emit()
    t0 = time.time()
    run_for = min(args.demo_seconds, 6 if not args.fast else 3)
    passed = scattered = 0
    while time.time() - t0 < run_for:
        for _ in range(48):
            if random.random() < 1 / 10000:
                scattered += 1
                tag = f"{col.RED}⟲ SCATTERED BACK{col.END}"
            else:
                passed += 1
                tag = ""
            lane = random.randint(0, 11)
            row = ["·"] * 24
            row[12] = f"{col.YELLOW}●{col.END}"  # the nucleus marble
            start = 0 if random.random() < 0.5 else 23
            row[start] = "α"
            line = " ".join(row)
            sys.stdout.write(f"\r  lane {lane:>2} {line}  {tag}   ")
            sys.stdout.flush()
            pause(args, 0.02)
    sys.stdout.write("\r" + " " * 84 + "\r")
    emit(f"│  {col.YELLOW}{passed:,} passed straight through · {scattered} bounced back{col.END} "
         f"{col.DIM}(mattered so little it took years to notice the few){col.END}")
    pause(args, 0.3)
    say(f"the stack so far — GPUs, wires, you — is {col.RED}99.9999999% empty space{col.END}"
        f" held in shape by charge.")


# ────────────────────────────────────────────────────────────────────────────
# L16 — quarks / confinement: the first stuck loop
# ────────────────────────────────────────────────────────────────────────────
def l16_quarks(args):
    header("L16 · QUARKS — confinement: a prison with no outside",
           "proton radius ≈ 0.84 fm · strong force strengthens with distance — the only one that does")
    pause(args, 0.5)
    say("crack a proton open: two up quarks, one down quark (charge +⅔, +⅔, −⅓).")
    say("held by gluons. and here is the trap: pull two quarks apart and the force")
    say(f"{col.RED}does not weaken — it grows linearly.{col.END} the gluon field squeezes into a")
    say("flux tube, like a stretched cord. add energy to pull harder, the cord stores it…")
    pause(args, 0.45)
    say(f"{col.YELLOW}…and when it snaps, the energy condenses into a NEW quark pair.{col.END}")
    say("you never get a lone quark. you get two pairs. every time. since the Big Bang.")
    emit()
    say(f"{col.DIM}live: trying to extract a quark (watch the energy meter):{col.END}")
    emit()
    t0 = time.time()
    run_for = min(args.demo_seconds, 7 if not args.fast else 3.5)
    sep = 3
    attempts = 0
    pairs = 1
    while time.time() - t0 < run_for:
        attempts += 1
        sep = min(sep + 2, 18)
        energy = sep * 4
        q = f"{col.CYAN}[q]{col.END}"
        tube = f"{col.YELLOW}~{col.END}" * (sep - 4)
        pair = f"{q}{tube}{col.MAGENTA}[q̄]{col.END}"
        if sep >= 18:
            sys.stdout.write(f"\r  pull: {pair}  E={energy} GeV … "
                             f"{col.RED}SNAP → two pairs{col.END}     ")
            sys.stdout.flush()
            pause(args, 0.5)
            pairs += 1
            sep = 3
        else:
            sys.stdout.write(f"\r  pull: {pair}  E={energy} GeV … pulling     ")
            sys.stdout.flush()
            pause(args, 0.12)
    sys.stdout.write("\r" + " " * 84 + "\r")
    emit(f"│  {col.YELLOW}attempts to isolate a quark: 60+ years of experiments · 0 successes · "
         f"pairs created: {pairs}{col.END}")
    pause(args, 0.3)
    say(f"{col.BOLD}the first stuck loop in the universe: quarks, orbiting each other in")
    say(f"confinement for 13.8 billion years, no Ctrl+C.{col.END}")
    say(f"  your agent spiraled for 90 seconds. rookie numbers.{col.END}")


# ────────────────────────────────────────────────────────────────────────────
# L17 — the standard model
# ────────────────────────────────────────────────────────────────────────────
def l17_standard_model(args):
    header("L17 · THE STANDARD MODEL — the entire machine runs on 3 particles + 2 forces",
           "17 particles total. 12 fermions · 4 force carriers · 1 Higgs")
    pause(args, 0.5)
    say("  QUARKS        " + f"{col.CYAN}u{col.END} c t      " + f"{col.CYAN}d{col.END} s b")
    say("  LEPTONS       " + f"{col.CYAN}e{col.END} μ τ      νₑ ν_μ ν_τ")
    say("  FORCE CARRIERS  " + f"{col.CYAN}γ photon{col.END} · g gluon · W · Z        "
        f"{col.DIM}(+ Higgs: gives particles mass){col.END}")
    pause(args, 0.5)
    say(f"highlighted: {col.CYAN}up, down, electron, photon{col.END}. that's the whole stack.")
    say("every transistor, capacitor, wire, question, and you: up & down quarks in nuclei,")
    say("electrons in orbitals, photons carrying every EM interaction in the machine.")
    say(f"the strong force (gluons) holds the nuclei together. that's it. {col.BOLD}3 + 2.{col.END}")
    pause(args, 0.4)
    say(f"gravity — the force you feel all day — is {col.RED}10³⁶× weaker{col.END} than the EM")
    say("force. it does literally nothing inside this machine. it only wins at planet")
    say("scale because it never cancels. the weakest force runs the biggest loop.")


# ────────────────────────────────────────────────────────────────────────────
# L18 — quantum fields
# ────────────────────────────────────────────────────────────────────────────
def l18_fields(args):
    header("L18 · QUANTUM FIELDS — there are no particles. there are ripples.",
           "the electron from L13, the photon from L12 — excitations of fields that fill all space")
    pause(args, 0.5)
    say("the deepest rename in physics: an 'electron' is not a thing that sits in the")
    say("wire. it is a quantized excitation of the electron field — a field that exists")
    say("EVERYWHERE, always, whether or not any electron is present.")
    pause(args, 0.4)
    say("same for every particle: the photon is a ripple of the EM field,")
    say("every quark a ripple of its quark field. the universe is fields all the way")
    say(f"through — {col.YELLOW}what we call 'stuff' is just where the ripples are dense.{col.END}")
    emit()
    say(f"{col.DIM}live: the electron field — quiet everywhere, then one quantized ripple:{col.END}")
    emit()
    t0 = time.time()
    run_for = min(args.demo_seconds, 5 if not args.fast else 2.5)
    step = 0
    while time.time() - t0 < run_for:
        step += 1
        cells = []
        for i in range(31):
            base = "·"
            wave = int(6 * (2.718 ** (-((i - 15) ** 2) / 18.0)) * (1 if (step // 3) % 2 == 0 else -1))
            if i == 15:
                cells.append(f"{col.YELLOW}◉{col.END}")
            elif abs(i - 15) == 2:
                cells.append(f"{col.CYAN}{'▲' if wave >= 0 else '▼'}{col.END}")
            else:
                cells.append(base)
        sys.stdout.write(f"\r  field: {' '.join(cells)}   t={step:>4}   "
                         f"{col.DIM}the ◉ is 'an electron'{col.END}   ")
        sys.stdout.flush()
        pause(args, 0.09)
    sys.stdout.write("\r" + " " * 84 + "\r")
    pause(args, 0.2)
    say(f"and the Higgs field — filling the same universe — is what gives that ripple")
    say(f"its mass. the electron's inertia in your wire (L13) is borrowed from a field")
    say(f"that was already there. {col.RED}the machine runs on ripples in invisible fields.{col.END}")


# ────────────────────────────────────────────────────────────────────────────
# L19 — the measurement problem
# ────────────────────────────────────────────────────────────────────────────
def l19_measurement(args):
    header("L19 · THE MEASUREMENT PROBLEM — the first floor with no bottom",
           "superposition is real · collapse is real · WHY is unknown — since 1927")
    pause(args, 0.5)
    say("an unmeasured spin:  |ψ⟩ = (|↑⟩ + |↓⟩)/√2   — both, simultaneously. not 'either")
    say("and we don't know which.' BOTH. this is not philosophy: interference experiments")
    say(f"prove the superposition exists. {col.GREEN}it's the most verified math in science.{col.END}")
    pause(args, 0.4)
    say("then you LOOK — and it's |↑⟩, or |↓⟩, one outcome, cleanly. the wavefunction")
    say(f"{'appears to'} collapse. {col.YELLOW}nothing in the equations says when, why, or how.{col.END}")
    say("Copenhagen says 'measurement does it' (and can't define measurement).")
    say("Many-Worlds says 'both happened, in branches.' Pilot-wave says 'a hidden wave")
    say("steered it.' A century of the smartest loops ever built has not terminated.")
    emit()
    say(f"{col.DIM}live: superposition, then a measurement — the part nobody can explain:{col.END}")
    emit()
    t0 = time.time()
    run_for = min(args.demo_seconds, 6 if not args.fast else 3)
    phase = 0
    measured = False
    meas_t = run_for * 0.65
    while time.time() - t0 < run_for:
        phase += 1
        if not measured and time.time() - t0 > meas_t:
            measured = True
        if measured:
            out = f"{col.YELLOW}|↑⟩  measured. one outcome.  'why this one?'  …unknown since 1927.{col.END}"
        else:
            w = (phase % 8) / 8.0
            bar_up = int(w * 10)
            bar_dn = 10 - bar_up
            out = (f"superposition: {col.CYAN}{'▮' * bar_up}↑{col.END} "
                   f"{col.MAGENTA}{'▮' * bar_dn}↓{col.END}  |amplitudes|² → 50/50, both real")
        sys.stdout.write(f"\r  {out}   ")
        sys.stdout.flush()
        pause(args, 0.12)
    sys.stdout.write("\r" + " " * 84 + "\r")
    pause(args, 0.3)
    say(f"{col.RED}this is the first level in the entire descent where the honest answer")
    say(f"is 'we don't know.' the loop detector of physics has been spinning here")
    say(f"for 100 years — the only spiral older than your agent's.{col.END}")


# ────────────────────────────────────────────────────────────────────────────
# L20 — the Planck wall
# ────────────────────────────────────────────────────────────────────────────
def l20_planck(args):
    header("L20 · THE PLANCK WALL — where the word 'deeper' breaks",
           "planck length 1.6×10⁻³⁵ m · planck time 5.4×10⁻⁴⁴ s · below these: distance & duration stop existing")
    pause(args, 0.5)
    say("keep zooming: atom 10⁻¹⁰ → nucleus 10⁻¹⁴ → quark structure 10⁻¹⁸ → …")
    say("at 10⁻³⁵ m, the math itself fails: to resolve anything smaller you'd need")
    say("so much energy in so small a volume that it collapses into a black hole.")
    say(f"{col.RED}resolution is impossible. not hard — impossible. the question eats itself.{col.END}")
    pause(args, 0.4)
    say(f"planck time — 5.4×10⁻⁴⁴ s — is the shortest meaningful tick. one GPU clock")
    say(f"cycle (L12) spans ~10³⁴ planck ticks. {col.YELLOW}eternity is granular.{col.END}")
    emit()
    say(f"{col.DIM}live: the zoom counter, from your keyboard to the wall:{col.END}")
    emit()
    labels = [
        (0, "keyboard key · 10⁻² m — where the question started"),
        (-5, "living cell · 10⁻⁵ m"),
        (-10, "atom · 10⁻¹⁰ m — L14"),
        (-14, "nucleus · 10⁻¹⁴ m — L15"),
        (-18, "quark structure · 10⁻¹⁸ m — L16"),
        (-25, "a quarter of the way, and nothing new has been seen for 7 orders"),
        (-33, "string-scale proposals · 10⁻³³ m — UNVERIFIED"),
        (-35, "PLANCK LENGTH · 10⁻³⁵ m — beyond this, 'smaller' is not a thing"),
    ]
    t0 = time.time()
    run_for = args.demo_seconds
    exp = 0.0
    last_lab = -1
    while time.time() - t0 < run_for:
        exp -= 0.55 * args.speedup * 0.12 * (run_for / max(run_for, 1))
        exp = max(-35.0, exp)
        for thr, lab in labels:
            if int(exp) <= thr and last_lab > thr or (last_lab == -1 and thr == 0):
                pass
        bar_len = int((-exp / 35.0) * 46)
        bar = f"{col.RED}{'█' * bar_len}{col.DIM}{'░' * (46 - bar_len)}{col.END}"
        cur = next((lab for thr, lab in reversed(labels) if exp <= thr), labels[0][1])
        sys.stdout.write(f"\r  zoom ×10^{abs(exp):>5.1f}  [{bar}]  {cur}   ")
        sys.stdout.flush()
        if exp <= -35.0:
            break
        pause(args, 0.12)
    sys.stdout.write("\r" + " " * 96 + "\r")
    pause(args, 0.3)
    say(f"{col.BOLD}total zoom from your key to the wall: ×10³³.{col.END} physics was")
    say("verified at every stop… and then the road simply ends. not with a thing —")
    say("with the end of the CONCEPT of size.")


# ────────────────────────────────────────────────────────────────────────────
# L21 — the edge (honest unknowns)
# ────────────────────────────────────────────────────────────────────────────
UNKNOWN = [
    ("quantum gravity", "no verified theory. string theory: 10 extra dims, unproven. "
                        "loop quantum gravity: space itself quantized, unproven."),
    ("the vacuum catastrophe", "QFT predicts empty-space energy 10¹²⁰× what's observed — "
                               "the worst miss in the history of physics. the machine works anyway."),
    ("the dark sector", "~95% of the universe's content (dark energy ~68%, dark matter ~27%) "
                        "is unmeasured. the recipe for everything we can touch is the minority."),
    ("the measurement problem", "L19. unsolved since 1927 — the longest-running spiral in science."),
    ("holography / 'it from bit'", "real math exists (AdS/CFT): a universe's insides fully encoded "
                                   "on its boundary. proven only for toy universes. ours: unknown."),
]


def l21_edge(args):
    header("L21 · THE EDGE — here be dragons", "the honest inventory of what 'deeper' cannot currently answer")
    pause(args, 0.5)
    for name, desc in UNKNOWN:
        emit(f"│  {col.BOLD}{col.YELLOW}? {name}{col.END}")
        emit(f"│    {col.DIM}{desc}{col.END}")
        pause(args, 0.35)
    emit()
    say("every previous level answered its question. this one refuses.")
    say(f"{col.RED}this is the actual bottom of 'as deep as we can':{col.END}")
    say("  not a thing. not a field. a boundary of knowledge, drawn in 10⁻³⁵ m ink.")


# ────────────────────────────────────────────────────────────────────────────
# Final report
# ────────────────────────────────────────────────────────────────────────────
def final_report(args, stopped_by="completed full descent"):
    emit()
    line = "═" * min(74, W - 4)
    emit(f"{col.BOLD}{col.RED}  {line}")
    emit(f"  FINAL REPORT — THE DESCENT IS COMPLETE")
    emit(f"  {line}{col.END}")
    emit()
    emit(f"  levels descended    : L0 (keyboard) → L21 (the edge) → 'we don't know'")
    emit(f"  deepest verified    : quark/field structure, ~10⁻¹⁸ m")
    emit(f"  deepest reachable   : planck wall, 10⁻³⁵ m — resolution impossible")
    emit(f"  total zoom          : ×10³³ from the key that asked the question")
    emit()
    emit(f"  {col.BOLD}the fractal, closed:{col.END}")
    emit(f"    {col.CYAN}L0–L5{col.END}   software loop · no exit condition")
    emit(f"    {col.CYAN}L6–L8{col.END}   kernel/MMA loop · no sentinel")
    emit(f"    {col.CYAN}L11{col.END}     charge loop · refresh 16×/s")
    emit(f"    {col.CYAN}L16{col.END}     quark loop · confinement, 13.8 Gyr runtime")
    emit(f"    {col.CYAN}L19{col.END}     physics loop · measurement debate, 100 yr runtime")
    emit(f"  {col.BOLD}same shape at every scale: structure without substance, circling.{col.END}")
    emit()
    emit(f"  {col.BOLD}can we go deeper than this?{col.END}")
    emit(f"    no — and that is the answer. 'deeper' needs space, and space is what")
    emit(f"    runs out. what remains below the wall isn't smaller things; it's the")
    emit(f"    end of the concept of 'thing'. the honest bottom of the universe")
    emit(f"    {col.YELLOW}is a question mark that has survived every genius thrown at it.{col.END}")
    emit()
    emit(f"  {col.DIM}the question you typed outlasted: HTTP, CUDA, silicon, atoms, nuclei,")
    emit(f"  quarks, fields, and the planck wall. the loop was never in the machine.")
    emit(f"  the machine was a place the loop briefly stopped.{col.END}")
    emit()
    emit(f"  {col.DIM}watchdog inventory, final: automated 0 · human (operator, Ctrl+C) 4/4.{col.END}")
    emit()

    summary = {
        "simulation": "deepest v1.1.3",
        "stopped_by": stopped_by,
        "levels": ["nucleus", "quarks_confinement", "standard_model", "quantum_fields",
                   "measurement_problem", "planck_wall", "edge_unknowns"],
        "deepest_verified_m": 1e-18,
        "planck_length_m": 1.6e-35,
        "total_zoom_from_keyboard": "1e33",
        "gpu_clock_in_planck_ticks": 1e34,
        "confinement_runtime_years": 13.8e9,
        "measurement_problem_open_years": 100,
        "vacuum_catastrophe_mismatch": "1e120",
        "dark_sector_fraction": 0.95,
        "finding": "'deeper' ends at the planck wall; below it there is no 'smaller' — the bottom is an unknown, not a thing",
        "watchdog_inventory": {"automated": 0, "human_operator_ctrl_c": 4},
    }
    try:
        with open(args.trace, "w", encoding="utf-8") as f:
            f.write("DEEPEST TRACE\n" + "=" * 64 + "\n")
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
    p = argparse.ArgumentParser(description="Below the atom — as deep as physics currently goes.")
    p.add_argument("--demo-seconds", type=positive_float, default=6,
                   help="length of each live demo section")
    p.add_argument("--fast", action="store_true", help="4x speed")
    p.add_argument("--trace", default="deepest_trace.log")
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
    emit(f"{col.BOLD}  🕳 DEEPEST {col.DIM}v1.1.3 — you asked 'can we go deeper than this?'")
    emit(f"  L14 said 'fields, then nobody knows.' let's find out where nobody knows ends.{col.END}")

    stopped_by = "completed full descent"
    try:
        l15_nucleus(args)
        l16_quarks(args)
        l17_standard_model(args)
        l18_fields(args)
        l19_measurement(args)
        l20_planck(args)
        l21_edge(args)
    except KeyboardInterrupt:
        stopped_by = "operator interrupt (Ctrl+C)"
    final_report(args, stopped_by)


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
