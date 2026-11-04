#!/usr/bin/env python3
"""Phase 6.3 lifecycle adapter adding the frozen PostgreSQL QR gate."""

from __future__ import annotations

import importlib.util
import pathlib
import sys


HERE = pathlib.Path(__file__).resolve().parent
BASE = HERE.parent / "bitora_5_8_2_phase_6_2" / "phase62_lifecycle.py"
SPEC = importlib.util.spec_from_file_location("bitora_phase62_lifecycle", BASE)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot load base lifecycle: {BASE}")
LIFECYCLE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LIFECYCLE)


if __name__ == "__main__":
    sys.argv.extend(["--postgres-access-concurrency", "1"])
    raise SystemExit(LIFECYCLE.main())
