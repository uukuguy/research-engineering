"""Check the existing persistence path used by method recovery, not agent intelligence."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from researchlog.tests.test_commands import CommandTestCase


class CapabilityRecoveryTests(CommandTestCase):
    def test_method_and_limits_survive_fresh_process_queries(self):
        piece = {
            "capability": "selected source retrieval",
            "entrypoint": "python probes/source_slice.py --manifest inputs/manifest.json",
            "input_identity": "fixture-manifest-v1",
            "artifact": "outputs/source-receipt.json",
            "limitations": ["source inspection only; no runtime execution"],
        }
        code, result = self.invoke([
            "current", "--set", "working_pieces=" + json.dumps([piece]),
        ])
        self.assertEqual(code, 0, result)
        capability = {
            "id": "CAP-source-slice-001",
            "capability": piece["capability"],
            "status": "LIMITED",
            "reuse_counter": 0,
            "supports_evidence": None,
            "notes": json.dumps(piece),
        }
        entry = self.root / "capability.json"
        entry.write_text(json.dumps(capability), encoding="utf-8")
        code, result = self.invoke(["env", "declare", "capability_map", str(entry)])
        self.assertEqual(code, 0, result)
        code, result = self.invoke(["validate"])
        self.assertEqual(code, 0, result)

        paths = [self.research("CURRENT.md"), self.research("ENVIRONMENT.md")]
        before = [p.read_bytes() for p in paths]
        cli_root = Path(__file__).resolve().parents[1]
        env = dict(os.environ, PYTHONPATH=str(cli_root.parent))

        def fresh(*args):
            run = subprocess.run(
                [sys.executable, str(cli_root), *args, "--json"],
                cwd=self.root, env=env, capture_output=True, text=True, timeout=15,
            )
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            return json.loads(run.stdout)["payload"]

        self.assertEqual(fresh("current")["current"]["working_pieces"], [piece])
        restored = fresh("env", "show")["environment"]["capability_map"]
        self.assertEqual(restored, [capability])
        self.assertEqual([p.read_bytes() for p in paths], before)
