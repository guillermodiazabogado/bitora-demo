#!/usr/bin/env python3

import importlib.util
import json
import pathlib
import tempfile
import unittest


HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("phase63_supervisor", HERE / "phase63_campaign_supervisor.py")
supervisor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(supervisor)


def report(gate: int) -> dict:
    return {
        "ok": True,
        "sha": "abc",
        "workspace_dirty": False,
        "configuration": {"postgres_access_concurrency_per_instance": gate},
        "levels": [{"access": {"sustained_qr_validation": {
            "profile": "valid", "closed_workers": 24, "duration_seconds": 600,
            "attempted": 10, "authorized": 10, "business_rejected": 0,
            "technical_errors": 0, "profile_pass": True,
            "responses_per_second": 81.0,
            "latency_ms": {"p95": 499.0},
        }}}],
        "checks": {"database_integrity": True, "containers_no_oom_or_restart": True},
        "integrity": {"postgres": {"deadlocks": 0}},
    }


class Phase63SupervisorTests(unittest.TestCase):
    def test_requires_frozen_conservative_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "report.json"
            path.write_text(json.dumps(report(1)), encoding="utf-8")
            self.assertTrue(all(supervisor.validate_report(path, "abc", "valid", 24).values()))
            path.write_text(json.dumps(report(2)), encoding="utf-8")
            checks = supervisor.validate_report(path, "abc", "valid", 24)
            self.assertFalse(checks["postgres_access_concurrency_exact"])


if __name__ == "__main__":
    unittest.main()
