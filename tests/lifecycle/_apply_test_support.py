from __future__ import annotations

import json
from pathlib import Path

from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH


def write_policy_and_manifest(package_root: Path) -> None:
    policy_path = package_root / DEFAULT_POLICY_PATH
    manifest_path = package_root / "template" / "setup" / "install-manifest.json"
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_text(
        json.dumps({"generationSettings": {"manifestOutput": "template/setup/install-manifest.json"}}),
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps(
            {
                "managedFiles": [
                    {
                        "id": "prompts.main",
                        "target": ".github/prompts/main.prompt.md",
                        "source": "template/main.prompt.md",
                        "strategy": "replace",
                        "hash": "sha256:source",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (package_root / "template" / "main.prompt.md").write_text("prompt\n", encoding="utf-8")