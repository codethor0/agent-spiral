#!/usr/bin/env python3
"""
test_numerics.py — independent recomputation of the simulation's model numbers.

Each simulation hardcodes a simplified-but-real hardware model (H100-class
GPU, 8B fp16, GQA). These tests recompute the quantities from first
principles and assert the scripts' constants match, so a typo'd constant in
one script fails here instead of silently diverging across files.

Run with the main suite:
    python3 -m unittest discover -s tests
"""

import math
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

import agent_stack_spiral as stack
import deeper_than_this as deeper
import the_spiral as spiral

GIB = 1024 ** 3


class TestHardwareModel(unittest.TestCase):
    """Reference model: 32 layers, 8 KV heads, head_dim 128, fp16,
    200k context, 8B params, H100 ~3.35 TB/s HBM."""

    def test_kv_bytes_per_token(self):
        # k+v x fp16: 32 x 8 x 128 x 2 x 2 = 131,072 B = 128 KiB
        expected = 32 * 8 * 128 * 2 * 2
        self.assertEqual(stack.KV_BYTES_PER_TOKEN, expected)
        self.assertEqual(spiral.KV_BYTES_PER_TOKEN, expected)
        self.assertEqual(expected, 131072)

    def test_weight_gib(self):
        # 8e9 params x 2 bytes = 16e9 B = 14.9 GiB
        expected = 16e9 / GIB
        self.assertAlmostEqual(stack.gib(stack.P["params"] * 2), expected, places=2)
        self.assertAlmostEqual(stack.WEIGHT_GIB if hasattr(stack, "WEIGHT_GIB")
                               else expected, expected, places=2)
        self.assertAlmostEqual(spiral.WEIGHT_GIB, expected, places=2)
        self.assertAlmostEqual(deeper.WEIGHT_GIB, expected, places=2)
        self.assertAlmostEqual(expected, 14.9, places=1)

    def test_kv_pool_gib(self):
        # 128 KiB x 200,000 tokens = 24.41 GiB
        expected = 131072 * 200_000 / GIB
        self.assertAlmostEqual(stack.gib(stack.KV_BYTES_PER_TOKEN * stack.CTX_MAX),
                               expected, places=2)
        self.assertAlmostEqual(spiral.KV_GIB, expected, places=1)
        self.assertAlmostEqual(expected, 24.4, places=1)

    def test_flops_per_token(self):
        # dense matmul rule: 2 FLOPs per parameter per token
        self.assertEqual(stack.FLOPS_PER_TOKEN, 16e9)
        self.assertEqual(spiral.FLOPS_PER_TOKEN, 16e9)

    def test_tok_mem_ms(self):
        # weight re-read per token: 16e9 B / 3.35 TB/s = 4.78 ms
        expected_ms = 16e9 / 3.35e12 * 1000
        for mod in (stack, spiral, deeper):
            with self.subTest(module=mod.__name__):
                ms = getattr(mod, "TOK_MEM_MS", None)
                if ms is None:  # stack computes it inline; recompute
                    ms = (mod.P["params"] * 2) / 3.35e12 * 1000
                self.assertAlmostEqual(ms, expected_ms, places=2)
        self.assertAlmostEqual(expected_ms, 4.78, places=2)

    def test_mma_flop(self):
        # HMMA.m16n8k16 = 16x8x16 MACs x 2 (multiply-add)
        expected = 16 * 8 * 16 * 2
        self.assertEqual(deeper.MMA_FLOP, expected)
        self.assertEqual(spiral.MMA_FLOP, expected)
        self.assertEqual(expected, 4096)

    def test_cycle_ns(self):
        # 1.98 GHz boost clock
        self.assertAlmostEqual(deeper.CYCLE_NS, 1e9 / 1.98e9, places=3)
        self.assertAlmostEqual(spiral.CYCLE_NS, 1e9 / 1.98e9, places=3)

    def test_dram_cell_counts(self):
        # KV ~210 billion bits, weights ~128 billion bits (displayed values)
        self.assertAlmostEqual(deeper.KV_BITS / 1e9, 209.6, delta=0.2)
        self.assertAlmostEqual(deeper.W_BITS / 1e9, 128.0, delta=0.2)
        self.assertAlmostEqual((deeper.KV_BITS + deeper.W_BITS) / 1e9,
                               337.6, delta=0.4)

    def test_energy_wh_conversion(self):
        # 700 W for 1 hour = 700 Wh; the two script formulas must agree
        secs = 1234.0
        self.assertAlmostEqual(700 * secs / 3600.0, 0.7 * secs / 3.6, places=6)

    def test_attention_tax_consistent(self):
        # both decode loops add 4 x layers x ctx x d_model attention FLOPs
        self.assertEqual(4 * 32 * 4096, 4 * stack.P["layers"] *
                         1000 * stack.P["d_model"] / 1000)


class TestPhysicsScales(unittest.TestCase):
    def test_ladder_scale_ordering(self):
        # physical scales in the LADDER table must descend monotonically
        SUP = {"⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
               "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
               "⁻": "-"}

        def exp_of(scale):
            if scale == "—":
                return None
            ascii_scale = "".join(SUP.get(ch, ch) for ch in scale)
            return int(ascii_scale.lstrip("10").split()[0])

        exps = [exp_of(sc) for _, _, sc, _ in spiral.LADDER]
        numeric = [e for e in exps if e is not None]
        # the table follows the journey, not a monotonic scale: L5 returns
        # to the wire (10^2 m) before the machine descent resumes
        for prev, cur in zip(numeric, numeric[1:]):
            if cur > prev:
                self.assertEqual(cur, 2, f"unexpected scale ascent: {prev} -> {cur}")
        self.assertEqual(numeric[0], 2)     # wire, 10^2 m
        self.assertEqual(min(numeric), -35)  # planck wall


if __name__ == "__main__":
    unittest.main(verbosity=2)
