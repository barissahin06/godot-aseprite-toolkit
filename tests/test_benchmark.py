import importlib.util
import json
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("duelist_benchmark", BASE / "benchmarks/sword_duelist/run.py")
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


class BenchmarkTests(unittest.TestCase):
    def test_contact_frame_boundary_and_recovery_hold(self):
        durations = benchmark.BRIEF["clips"]["attack"]["durations_ms"]
        self.assertEqual(benchmark.selected_frame(0.279, durations), 4)
        self.assertEqual(benchmark.selected_frame(0.28, durations), 5)
        self.assertEqual(benchmark.selected_frame(0.70, durations), 11)
        self.assertEqual(benchmark.selected_frame(0.959, durations), 11)
        self.assertEqual(benchmark.selected_frame(0.96, durations), 0)

    def test_common_loops_and_single_attack_contract(self):
        brief = json.loads((BASE / "benchmarks/sword_duelist/brief.json").read_text())
        self.assertEqual(sum(brief["clips"]["idle"]["durations_ms"]), 960)
        self.assertEqual(sum(brief["clips"]["walk"]["durations_ms"]), 960)
        self.assertEqual(sum(brief["clips"]["attack"]["durations_ms"]), 700)
        self.assertFalse(brief["clips"]["attack"]["loop"])
        self.assertLess(brief["clips"]["attack"]["contact_seconds"], brief["clips"]["attack"]["chain_ready_seconds"])


if __name__ == "__main__":
    unittest.main()
