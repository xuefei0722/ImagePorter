"""Tests for imageporter.constants — sanity checks on configuration values."""

from __future__ import annotations

import unittest

from imageporter.constants import (
    ARCH_REFERENCE_ROWS,
    MAX_CONCURRENCY,
    MAX_LOG_LINES,
    MIN_CONCURRENCY,
    PLATFORM_LABELS,
    PLATFORM_OPTIONS,
    SIDEBAR_WIDTH,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)


class TestConstants(unittest.TestCase):
    def test_window_dimensions_positive(self):
        self.assertGreater(WINDOW_WIDTH, 0)
        self.assertGreater(WINDOW_HEIGHT, 0)
        self.assertGreater(SIDEBAR_WIDTH, 0)
        self.assertLess(SIDEBAR_WIDTH, WINDOW_WIDTH)

    def test_concurrency_bounds(self):
        self.assertGreaterEqual(MIN_CONCURRENCY, 1)
        self.assertGreaterEqual(MAX_CONCURRENCY, MIN_CONCURRENCY)

    def test_log_lines_positive(self):
        self.assertGreater(MAX_LOG_LINES, 0)

    def test_platform_options_non_empty(self):
        self.assertGreater(len(PLATFORM_OPTIONS), 0)

    def test_labels_cover_all_options(self):
        for opt in PLATFORM_OPTIONS:
            self.assertIn(opt, PLATFORM_LABELS, f"Missing label for {opt}")

    def test_reference_rows_cover_all_options(self):
        arch_platforms = {row[0] for row in ARCH_REFERENCE_ROWS}
        for opt in PLATFORM_OPTIONS:
            self.assertIn(opt, arch_platforms, f"Missing reference row for {opt}")

    def test_labels_are_two_tuples(self):
        for key, val in PLATFORM_LABELS.items():
            self.assertIsInstance(val, tuple)
            self.assertEqual(len(val), 2, f"PLATFORM_LABELS[{key!r}] should be a 2-tuple")


if __name__ == "__main__":
    unittest.main()
