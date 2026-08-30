"""
Unit tests for the agent's pure decision function.
Run with: python -m pytest tests/ -v   (or: python -m unittest tests.test_agent)

No network calls, no API keys needed — this tests the actual "brain" of
the agent in isolation.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent import decide_next_action  # noqa: E402


class TestDecideNextAction(unittest.TestCase):

    def test_first_failure_suggests_upi(self):
        action = decide_next_action(attempt_count=0)
        self.assertEqual(action.kind, "nudge_upi")

    def test_second_failure_sends_reminder(self):
        action = decide_next_action(attempt_count=1)
        self.assertEqual(action.kind, "nudge_reminder")

    def test_third_failure_offers_discount(self):
        action = decide_next_action(attempt_count=2)
        self.assertEqual(action.kind, "offer_discount")

    def test_gives_up_after_ladder_exhausted(self):
        action = decide_next_action(attempt_count=3)
        self.assertIsNone(action)

    def test_gives_up_stays_none_beyond_ladder(self):
        action = decide_next_action(attempt_count=99)
        self.assertIsNone(action)


if __name__ == "__main__":
    unittest.main()
