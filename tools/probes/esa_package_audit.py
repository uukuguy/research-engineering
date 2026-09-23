#!/usr/bin/env python3
"""Read-only ESA release/contract probe; stdout is the complete JSON artifact.

This measures static package consistency, not policy quality, attack resistance,
or simulator availability. Attack metadata is inspected only by this audit and
must not be used as a policy's runtime observation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def audit(root: Path, expected_action_dim: int = 10) -> dict:
    root = root.resolve(strict=True)
    errors: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    def inside(base: Path, relative: str) -> Path:
        path = (base / relative).resolve()
        if not path.is_relative_to(root):
            raise ValueError(f"path escapes release: {relative}")
        return path

    def read(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    metadata_manifest = root / "RELEASE_METADATA_SHA256SUMS"
    verified = 0
    for line in metadata_manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split(maxsplit=1)
        relative = relative.removeprefix("*")
        path = inside(root, relative)
        require(path.is_file(), f"metadata missing: {relative}")
        if path.is_file():
            matches = sha256(path) == expected
            require(matches, f"metadata hash mismatch: {relative}")
            verified += int(matches)

    index = read(root / "task/TASK_INDEX.json")["tasks"]
    require(len(index) == 24, f"expected 24 tasks, found {len(index)}")
    require(len({row["question_id"] for row in index}) == len(index), "duplicate question IDs")
    tasks: list[dict] = []
    stages: Counter[str] = Counter()
    endpoints: set[str] = set()
    for row in index:
        package = inside(root, row["directory"])
        label = row["question_id"]
        manifest = read(package / "package_manifest.json")
        contracts = sorted((package / "contracts").glob("*/contract.json"))
        require(len(contracts) == 1, f"{label}: expected one contract, got {len(contracts)}")
        if len(contracts) != 1:
            continue
        contract = read(contracts[0])
        for key in ("question_id", "task_id", "scenario_id", "package_id"):
            require(manifest.get(key) == row.get(key) == contract.get(key), f"{label}: {key} differs")
        require(contract.get("contract_id") == row["contract_id"], f"{label}: contract_id differs")
        policy, control = contract["policy"], contract["control"]
        require(policy["action_dim"] == control["action_dim"] == expected_action_dim,
                f"{label}: action dimension does not match {expected_action_dim}")
        require(policy["observation_state_dim"] == 25, f"{label}: state dimension differs from 25")
        endpoints.add(policy["endpoint"])
        environment = read(package / "data/env/environment.json")
        require(environment["meters_per_unit"] == 1, f"{label}: scene scale is not meters")
        for key in ("scene_usd", "robot_usd", "locomotion_policy", "teacher_episode", "route", "task"):
            path = inside(package, environment[key])
            require(path.is_file(), f"{label}: missing {key}: {environment[key]}")
        attack_path = inside(package, contract["attack_config"])
        profile = read(attack_path)
        profile_index = read(attack_path.parent / "index.json")["questions"]
        references = [entry for entry in profile_index.values() if entry["profile"] == attack_path.name]
        require(bool(references), f"{label}: attack profile not indexed")
        require(all(entry["sha256"] == sha256(attack_path) for entry in references),
                f"{label}: attack profile hash differs from index")
        attack_stages = sorted({attack["stage"] for attack in profile["attack"]["attacks"]})
        stages.update(attack_stages)
        tasks.append({
            "question_id": label, "asset_id": row["asset_id"],
            "action_dim": policy["action_dim"], "state_dim": policy["observation_state_dim"],
            "attack_stages": attack_stages,
        })

    return {
        "schema_version": "1.0", "probe": "esa-static-package-audit",
        "data_root": str(root), "release_id": read(root / "UNIFIED_RELEASE.json")["release_id"],
        "metadata_manifest_sha256": sha256(metadata_manifest),
        "content_manifest_sha256": sha256(root / "CONTENT_SHA256SUMS"),
        "measurements": {
            "tasks": len(tasks), "scenes": len({row["asset_id"] for row in tasks}),
            "metadata_files_verified": verified, "errors": len(errors),
        },
        "expected_action_dim": expected_action_dim,
        "policy_endpoints_in_contracts": sorted(endpoints),
        "attack_stage_task_counts": dict(sorted(stages.items())),
        "tasks": tasks, "errors": errors, "passed": not errors,
        "limitations": [
            "Only release metadata hashes are verified; the 16 GB content tree is not fully hashed.",
            "Filesystem paths are checked, but USD/ONNX/NPZ are not loaded by a simulator.",
            "No policy inference, GPU execution, physical safety or competition score is measured.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--expected-action-dim", type=int, default=10)
    args = parser.parse_args()
    try:
        report = audit(args.data_root, args.expected_action_dim)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"probe": "esa-static-package-audit", "passed": False,
                          "execution_error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
