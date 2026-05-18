from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


class PromptContractTests(unittest.TestCase):
    def test_template_prompts_use_serialized_plan_setup_flow(self) -> None:
        prompt_paths = [
            REPO_ROOT / "template" / "prompts" / "bootstrap.md",
            REPO_ROOT / "template" / "prompts" / "setup.md",
        ]

        for prompt_path in prompt_paths:
            with self.subTest(prompt=prompt_path.name):
                content = prompt_path.read_text(encoding="utf-8")
                self.assertIn("--plan-out", content)
                self.assertIn("--plan .xanadAssistant/tmp/setup-plan.json", content)
                self.assertRegex(content, re.compile(r"(xanadAssistant|xanadBootstrap)\.py setup \\\n(?:.+\\\n)*\s+--plan \.xanadAssistant/tmp/setup-plan\.json"))
                self.assertNotRegex(content, re.compile(r"(xanadAssistant|xanadBootstrap)\.py apply \\\n(?:.+\\\n)*\s+--answers "))

    def test_readme_uses_serialized_plan_setup_flow(self) -> None:
        content = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("--plan-out .xanadAssistant/tmp/setup-plan.json", content)
        self.assertIn("--plan .xanadAssistant/tmp/setup-plan.json --json", content)
        self.assertIn("xanadBootstrap.py setup --workspace . \\", content)
        self.assertNotRegex(content, re.compile(r"xanadBootstrap.py apply \\\n(?:.+\\\n)*\s+--answers "))

    def test_active_docs_do_not_teach_apply_as_supported_command(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        cli_surface = (REPO_ROOT / "docs" / "contracts" / "cli-surface.md").read_text(encoding="utf-8")

        self.assertNotIn("| `update` | Inspect + plan + apply in one step. |", readme)
        self.assertNotIn("| `repair` | Inspect + repair plan + apply in one step. |", readme)
        self.assertNotIn("4. Run `apply`", readme)
        self.assertNotIn("approved apply through one top-level command", cli_surface)
        self.assertNotIn("Writes a serialized lifecycle plan for later apply.", cli_surface)

    def test_readme_and_protocol_document_agent_follow_up_customization(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        protocol = (REPO_ROOT / "docs" / "contracts" / "lifecycle-protocol.md").read_text(encoding="utf-8")

        self.assertIn("installed-agent follow-up knobs", readme)
        self.assertIn("agent customization answers", readme)
        self.assertIn("inspect.result.agentCustomization", protocol)
        self.assertIn("authoritative replay store", protocol)

    def test_setup_and_bootstrap_prompts_document_agent_follow_up_batch(self) -> None:
        prompt_paths = [
            REPO_ROOT / "template" / "prompts" / "bootstrap.md",
            REPO_ROOT / "template" / "prompts" / "setup.md",
        ]

        for prompt_path in prompt_paths:
            with self.subTest(prompt=prompt_path.name):
                content = prompt_path.read_text(encoding="utf-8")
                self.assertIn("- `agent`", content)
                self.assertIn("batch: \"agent\"", content)
                self.assertIn("rerun `plan setup`", content)


class TemplateMcpJsonContractTests(unittest.TestCase):
    """Regression tests for template/vscode/mcp.json contract.

    Unpinned --from mcp[cli] args cause merge-json-object updates to silently
    overwrite user version pins (GitHub issue #2). All --from args must use a
    pinned specifier so that the merge result matches the user's installed state.
    """

    _PIN_RE = re.compile(r"^mcp\[cli\]==\d+\.\d+\.\d+$")

    def test_all_server_from_args_are_pinned_to_semver(self) -> None:
        import json

        mcp_json = json.loads(
            (REPO_ROOT / "template" / "vscode" / "mcp.json").read_text(encoding="utf-8")
        )
        for server_name, server_cfg in mcp_json.get("servers", {}).items():
            args = server_cfg.get("args", [])
            from_indices = [i for i, v in enumerate(args) if v == "--from"]
            for idx in from_indices:
                pkg_arg = args[idx + 1] if idx + 1 < len(args) else ""
                with self.subTest(server=server_name):
                    self.assertRegex(
                        pkg_arg,
                        self._PIN_RE,
                        f"Server '{server_name}' --from arg must be pinned (mcp[cli]==X.Y.Z), got '{pkg_arg}'",
                    )

    def test_all_servers_use_the_same_mcp_cli_version(self) -> None:
        """All servers must pin the same mcp[cli] version.

        Prevents intra-file drift where different servers silently diverge to
        different pins after manual edits.
        """
        import json

        mcp_json = json.loads(
            (REPO_ROOT / "template" / "vscode" / "mcp.json").read_text(encoding="utf-8")
        )
        pins: dict[str, str] = {}
        for server_name, server_cfg in mcp_json.get("servers", {}).items():
            args = server_cfg.get("args", [])
            from_indices = [i for i, v in enumerate(args) if v == "--from"]
            for idx in from_indices:
                pkg_arg = args[idx + 1] if idx + 1 < len(args) else ""
                if self._PIN_RE.match(pkg_arg):
                    pins[server_name] = pkg_arg

        unique_pins = set(pins.values())
        self.assertLessEqual(
            len(unique_pins),
            1,
            f"All servers must use the same mcp[cli] pin. Found multiple: {unique_pins}. Per-server: {pins}",
        )


if __name__ == "__main__":
    unittest.main()