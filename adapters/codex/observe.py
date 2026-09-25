#!/usr/bin/env python3
"""Observation entry point, beside hook.py and outside its dispatcher; see harness_core.observer."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
from harness_core.observer import main
if __name__ == "__main__":
    main("codex")
