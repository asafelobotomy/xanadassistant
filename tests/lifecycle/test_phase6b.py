from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests._test_base import XanadTestBase


class XanadAssistantPhase6Tests(XanadTestBase):
    """Phase 6: source resolution, integrity, stale-version, incomplete-install, dry-run."""

    def _apply(self, workspace: Path) -> dict:
        """Run a full apply in workspace and return the parsed payload."""
        result = self._run("apply", "--json", "--non-interactive", workspace=workspace)
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout)

    # ------------------------------------------------------------------
    # Source parsing – unit tests
    # ------------------------------------------------------------------
    def test_stale_version_warning_appears_in_inspect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._apply(workspace)

            lockfile_path = workspace / ".github" / "xanadAssistant-lock.json"
            lockfile = json.loads(lockfile_path.read_text(encoding="utf-8"))
            lockfile["manifest"]["hash"] = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
            lockfile_path.write_text(json.dumps(lockfile, indent=2), encoding="utf-8")

            result = self._run("inspect", "--json", workspace=workspace)
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)

            warning_codes = [w["code"] for w in payload.get("warnings", [])]
            self.assertIn("package_version_changed", warning_codes)

    # ------------------------------------------------------------------
    # Incomplete-install – subprocess tests
    # ------------------------------------------------------------------

    def test_incomplete_install_appears_as_repair_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._apply(workspace)

            (workspace / ".github" / "copilot-instructions.md").unlink()

            result = self._run("plan", "repair", "--json", "--non-interactive", workspace=workspace)
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn("incomplete-install", payload["result"]["repairReasons"])

    def test_repair_fixes_incomplete_install(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._apply(workspace)

            (workspace / ".github" / "copilot-instructions.md").unlink()

            result = self._run("repair", "--json", "--non-interactive", workspace=workspace)
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("ok", payload["status"])
            self.assertEqual("passed", payload["result"]["validation"]["status"])
            self.assertTrue((workspace / ".github" / "copilot-instructions.md").exists())

    # ------------------------------------------------------------------
    # Dry-run – subprocess test
    # ------------------------------------------------------------------

    def test_dry_run_apply_skips_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            result = self._run("apply", "--json", "--non-interactive", "--dry-run", workspace=workspace)
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["result"].get("dryRun"), "Expected dryRun=True in result")
            self.assertFalse(
                (workspace / ".github" / "copilot-instructions.md").exists(),
                "Dry-run should not write managed files",
            )
            self.assertFalse(
                (workspace / ".github" / "xanadAssistant-lock.json").exists(),
                "Dry-run should not write lockfile",
            )

    def test_dry_run_apply_reports_planned_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            result = self._run("apply", "--json", "--non-interactive", "--dry-run", workspace=workspace)
            payload = json.loads(result.stdout)
            # Planned writes should be > 0 (files would be added)
            writes = payload["result"]["writes"]
            total = sum(writes.values())
            self.assertGreater(total, 0, "Dry-run should still report planned write counts")

    # ------------------------------------------------------------------
    # Lockfile package field – subprocess test
    # ------------------------------------------------------------------

    def test_lockfile_package_field_has_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._apply(workspace)
            lockfile = json.loads((workspace / ".github" / "xanadAssistant-lock.json").read_text())
            self.assertEqual("xanadAssistant", lockfile["package"]["name"])

    # ------------------------------------------------------------------
    # Phase 7 – agent and prompt file checks
    # ------------------------------------------------------------------

    def test_agent_file_has_lifecycle_commands(self) -> None:
        agent_text = (self.REPO_ROOT / "agents" / "xanad-lifecycle.agent.md").read_text(encoding="utf-8")
        for term in ("inspect", "apply", "update", "repair", "factory-restore"):
            self.assertIn(term, agent_text, f"Agent file missing lifecycle command: {term}")

    def test_agent_file_has_trigger_phrases(self) -> None:
        agent_text = (self.REPO_ROOT / "agents" / "xanad-lifecycle.agent.md").read_text(encoding="utf-8")
        self.assertIn("Trigger phrases", agent_text)

    def test_setup_prompt_has_workflow_steps(self) -> None:
        prompt_text = (self.REPO_ROOT / "template" / "prompts" / "setup.md").read_text(encoding="utf-8")
        for step in ("inspect", "plan", "apply"):
            self.assertIn(step, prompt_text, f"Setup prompt missing workflow step: {step}")

    def test_setup_prompt_references_dry_run(self) -> None:
        prompt_text = (self.REPO_ROOT / "template" / "prompts" / "setup.md").read_text(encoding="utf-8")
        self.assertIn("dry-run", prompt_text.lower())

    def test_setup_prompt_references_predecessor_migration(self) -> None:
        prompt_text = (self.REPO_ROOT / "template" / "prompts" / "setup.md").read_text(encoding="utf-8")
        self.assertIn("copilot-instructions-template", prompt_text)
        self.assertIn("plan repair", prompt_text)
        self.assertIn("repair", prompt_text)

    def test_setup_prompt_references_mcp_lifecycle_tools(self) -> None:
        prompt_text = (self.REPO_ROOT / "template" / "prompts" / "setup.md").read_text(encoding="utf-8")
        self.assertIn("xanadTools", prompt_text)
        self.assertIn("lifecycle_plan_setup", prompt_text)

    def test_lifecycle_agent_references_mcp_lifecycle_tools(self) -> None:
        agent_text = (self.REPO_ROOT / "agents" / "xanad-lifecycle.agent.md").read_text(encoding="utf-8")
        self.assertIn("lifecycle_inspect", agent_text)
        self.assertIn("xanadTools", agent_text)

    def test_lifecycle_agent_frontmatter_enables_delegation(self) -> None:
        agent_text = (self.REPO_ROOT / "agents" / "xanad-lifecycle.agent.md").read_text(encoding="utf-8")
        self.assertIn("tools: [agent, codebase, search, runCommands, askQuestions]", agent_text)
        self.assertIn("agents: [Explore, Debugger, Planner]", agent_text)
        self.assertIn("model:", agent_text)

    def test_debugger_planner_researcher_and_docs_agents_exist_with_core_roles(self) -> None:
        debugger_text = (self.REPO_ROOT / "agents" / "debugger.agent.md").read_text(encoding="utf-8")
        docs_text = (self.REPO_ROOT / "agents" / "docs.agent.md").read_text(encoding="utf-8")
        planner_text = (self.REPO_ROOT / "agents" / "planner.agent.md").read_text(encoding="utf-8")
        researcher_text = (self.REPO_ROOT / "agents" / "researcher.agent.md").read_text(encoding="utf-8")

        self.assertIn("Your role: diagnose failures before implementation starts.", debugger_text)
        self.assertIn("Prefer targeted commands and tests", debugger_text)
        self.assertIn("user-invocable: false", debugger_text)

        self.assertIn("Your role: turn medium or large requests into scoped execution plans", planner_text)
        self.assertIn("Stay read-only. Do not modify files.", planner_text)
        self.assertIn("user-invocable: false", planner_text)

        self.assertIn("Your role: gather source-backed information", researcher_text)
        self.assertIn("Prefer primary sources", researcher_text)
        self.assertIn("user-invocable: false", researcher_text)

        self.assertIn("Your role: write and update documentation", docs_text)
        self.assertIn("Prefer documentation files, guides, prompts, instructions", docs_text)
        self.assertIn("user-invocable: true", docs_text)

    def test_template_uses_canonical_lifecycle_agent_name(self) -> None:
        instructions_text = (self.REPO_ROOT / "template" / "copilot-instructions.md").read_text(encoding="utf-8")
        self.assertIn("xanad-lifecycle", instructions_text)
        self.assertNotIn("`lifecycle-planning` agent", instructions_text)

    def test_instructions_route_debugging_planning_research_and_docs_to_specialists(self) -> None:
        instructions_text = (self.REPO_ROOT / "template" / "copilot-instructions.md").read_text(encoding="utf-8")
        self.assertIn("Root-cause diagnosis, failing tests", instructions_text)
        self.assertIn("Complex multi-step planning, phased rollout", instructions_text)
        self.assertIn("External documentation, upstream behavior", instructions_text)
        self.assertIn("Documentation updates, migration notes", instructions_text)
        self.assertIn("`Debugger`", instructions_text)
        self.assertIn("`Docs`", instructions_text)
        self.assertIn("`Planner`", instructions_text)
        self.assertIn("`Researcher`", instructions_text)

    # ------------------------------------------------------------------
    # Phase 8 – UI / agent progress
    # ------------------------------------------------------------------

    def test_agent_progress_apply_includes_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            result = self._run(
                "apply", "--non-interactive", "--ui", "agent", "--json", workspace=workspace
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("Receipt", result.stderr)

    def test_agent_progress_apply_includes_validate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            result = self._run(
                "apply", "--non-interactive", "--ui", "agent", "--json", workspace=workspace
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("Validate", result.stderr)

    def test_dry_run_agent_progress_notes_no_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            result = self._run(
                "apply", "--non-interactive", "--dry-run", "--ui", "agent", "--json", workspace=workspace
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("Dry run", result.stderr)

    def test_log_file_written_when_flag_is_passed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            log_path = Path(tmp) / "lifecycle.log"
            result = self._run(
                "apply", "--non-interactive", "--ui", "agent", "--json",
                "--log-file", str(log_path),
                workspace=workspace,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue(log_path.exists(), "Log file should have been created")
            log_text = log_path.read_text(encoding="utf-8")
            self.assertIn("xanadAssistant", log_text)
            self.assertIn("Apply", log_text)
            self.assertIn("Receipt", log_text)



if __name__ == "__main__":
    unittest.main()
