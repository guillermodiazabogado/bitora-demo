#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import pathlib
import tempfile
import unittest


HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("phase62_supervisor", HERE / "phase62_campaign_supervisor.py")
assert SPEC and SPEC.loader
supervisor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(supervisor)


class SupervisorTests(unittest.TestCase):
    def test_stage_order_is_strict(self):
        self.assertEqual(
            [item["id"] for item in supervisor.stages()],
            [
                "qr-valid-24-r1", "qr-valid-24-r2", "qr-valid-24-r3",
                "qr-antipassback-16-r1", "qr-antipassback-16-r2", "qr-antipassback-16-r3",
                "qr-antipassback-24-r1", "qr-antipassback-24-r2", "qr-antipassback-24-r3",
            ],
        )

    def test_atomic_checkpoint_is_valid_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = pathlib.Path(temporary) / "checkpoint.json"
            for index in range(50):
                supervisor.atomic_json(path, {"index": index})
                self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["index"], index)

    def test_valid_semantics(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = pathlib.Path(temporary) / "report.json"
            path.write_text(json.dumps(_report("valid", 24, 5, 0)), encoding="utf-8")
            self.assertTrue(all(supervisor.validate_report(path, "abc", "valid", 24).values()))

    def test_antipassback_semantics(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = pathlib.Path(temporary) / "report.json"
            path.write_text(json.dumps(_report("antipassback", 16, 0, 5)), encoding="utf-8")
            self.assertTrue(all(supervisor.validate_report(path, "abc", "antipassback", 16).values()))

    def test_p95_failure_stops_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = pathlib.Path(temporary) / "report.json"
            report = _report("valid", 24, 5, 0)
            report["levels"][0]["access"]["sustained_qr_validation"]["latency_ms"]["p95"] = 500.001
            path.write_text(json.dumps(report), encoding="utf-8")
            self.assertFalse(supervisor.validate_report(path, "abc", "valid", 24)["p95_under_500ms"])


def _report(mode: str, readers: int, authorized: int, rejected: int) -> dict:
    return {
        "ok": True, "sha": "abc", "workspace_dirty": False,
        "levels": [{"access": {"sustained_qr_validation": {
            "profile": mode, "closed_workers": readers, "duration_seconds": 600,
            "attempted": authorized + rejected, "authorized": authorized,
            "business_rejected": rejected, "technical_errors": 0,
            "latency_ms": {"p95": 499.9}, "profile_pass": True,
        }}}],
        "checks": {"database_integrity": True, "containers_no_oom_or_restart": True},
        "integrity": {"postgres": {"deadlocks": 0}},
    }


if __name__ == "__main__":
    unittest.main()
