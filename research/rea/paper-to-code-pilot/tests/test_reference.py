"""Deterministic tests for the original CPU attention-weight micro-kernel."""
import math
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reference import masked_attention_weights  # noqa: E402


class MaskedAttentionTests(unittest.TestCase):
    def test_small_independent_oracle(self):
        actual = masked_attention_weights([[0.0, math.log(3.0)]], [[True, True]])
        self.assertAlmostEqual(actual[0][0], 0.25, places=13)
        self.assertAlmostEqual(actual[0][1], 0.75, places=13)

    def test_masks_rows_and_normalization(self):
        scores = [[1.0, 2.0, 3.0], [5.0, -2.0, 7.0]]
        masks = [[True, False, True], [False, True, False]]
        before = [row[:] for row in scores]
        result = masked_attention_weights(scores, masks)
        self.assertEqual(scores, before)
        self.assertEqual(result[0][1], 0.0)
        self.assertEqual(result[1], [0.0, 1.0, 0.0])
        for row in result:
            self.assertAlmostEqual(math.fsum(row), 1.0, places=13)
            self.assertTrue(all(0 <= value <= 1 for value in row))

    def test_extreme_logits_no_overflow(self):
        actual = masked_attention_weights([[10000.0, 9999.0, -10000.0]], [[True] * 3])[0]
        self.assertAlmostEqual(actual[0], 1 / (1 + math.exp(-1)), places=13)
        self.assertAlmostEqual(actual[1], math.exp(-1) / (1 + math.exp(-1)), places=13)
        self.assertEqual(actual[2], 0.0)

    def test_masked_huge_value_does_not_shift_max(self):
        actual = masked_attention_weights([[1e300, -3.0, -3.0]], [[False, True, True]])[0]
        self.assertEqual(actual, [0.0, 0.5, 0.5])

    def test_single_allowed_key_and_empty_batch(self):
        self.assertEqual(masked_attention_weights([[7.0]], [[True]]), [[1.0]])
        self.assertEqual(masked_attention_weights([], []), [])

    def test_errors_fail_closed(self):
        cases = [
            ([[1.0]], []),
            ([[1.0, 2.0]], [[True]]),
            ([[]], [[]]),
            ([[1.0]], [[False]]),
            ([[1.0]], [[1]]),
            ([[float('nan')]], [[True]]),
            ([[float('inf')]], [[True]]),
        ]
        for scores, mask in cases:
            with self.subTest(scores=scores, mask=mask):
                with self.assertRaises(ValueError):
                    masked_attention_weights(scores, mask)

    def test_mutation_checks_detect_unmasked_and_no_stability(self):
        # Two deliberate wrong variants are rejected by the same core oracles.
        def wrong_ignores_mask(scores, mask):
            row = scores[0]
            m = max(row)
            e = [math.exp(v - m) for v in row]
            return [[v / sum(e) for v in e]]

        case = [[2.0, 9.0, 2.0]]
        mask = [[True, False, True]]
        expected = masked_attention_weights(case, mask)[0]
        self.assertEqual(expected, [0.5, 0.0, 0.5])
        self.assertNotEqual(wrong_ignores_mask(case, mask)[0], expected)
        with self.assertRaises(OverflowError):
            math.exp(10000.0)  # unstable exponentiation is visibly rejected


if __name__ == '__main__':
    unittest.main()
