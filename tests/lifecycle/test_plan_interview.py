from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.lifecycle._xanad import _interview
from scripts.lifecycle._xanad._errors import LifecycleCommandError

class InterviewAnswerResolutionTests(unittest.TestCase):
    def _assert_load_answers_error(self, path: str | None) -> LifecycleCommandError:
        with self.assertRaises(LifecycleCommandError) as excinfo:
            _interview.load_answers(path)
        return excinfo.exception

    def _interview_context(self, policy: dict[str, object], metadata: dict[str, object]) -> dict[str, object]:
        agent_managed_files = []
        for agent in metadata.get("agentRegistry", {}).get("agents", []):
            if agent.get("status") != "active":
                continue
            agent_managed_files.append(
                {
                    "id": agent["manifestEntryId"],
                    "surface": "agents",
                    "ownership": ["local", "plugin-backed-copilot-format"],
                    "requiredWhen": [],
                }
            )
        return {
            "policy": policy,
            "metadata": metadata,
            "manifest": {"managedFiles": agent_managed_files},
            "lockfileState": {},
            "warnings": ["warn"],
            "installState": "installed",
            "metadataArtifacts": {"policy": {"loaded": True}},
        }

    def test_build_interview_questions_and_result_cover_setup_update_and_other_modes(self) -> None:
        policy = {
            "ownershipDefaults": {"agents": "local", "skills": "plugin-backed-copilot-format"},
            "canonicalSurfaces": ["mcp-config"],
        }
        metadata = {
            "profileRegistry": {"profiles": [{"id": "balanced", "status": "active"}, {"id": "old", "status": "retired"}]},
            "packRegistry": {"packs": [{"id": "tdd", "optional": True, "status": "active"}, {"id": "dead", "optional": True, "status": "retired"}]},
            "agentRegistry": {
                "agents": [
                    {
                        "id": "commit",
                        "status": "active",
                        "manifestEntryId": "agents.commit.agent.md",
                        "customization": {
                            "requiresInstalled": True,
                            "tokenNamespace": "agent:commit",
                            "questions": [
                                {
                                    "id": "message-style",
                                    "answerKey": "agent.commit.messageStyle",
                                    "kind": "choice",
                                    "options": ["conventional-with-context", "conventional-subject-first"],
                                },
                                {
                                    "id": "secret-guard-mode",
                                    "answerKey": "agent.commit.secretGuardMode",
                                    "kind": "choice",
                                    "options": ["surface-and-stop", "refuse-on-probable-secret"],
                                },
                            ],
                        },
                    },
                    {
                        "id": "docs",
                        "status": "active",
                        "manifestEntryId": "agents.docs.agent.md",
                        "customization": {
                            "requiresInstalled": True,
                            "tokenNamespace": "agent:docs",
                            "questions": [
                                {
                                    "id": "output-style",
                                    "answerKey": "agent.docs.outputStyle",
                                    "kind": "choice",
                                    "options": ["corpus-match", "concise-guides"],
                                }
                            ],
                        },
                    },
                    {
                        "id": "planner",
                        "status": "active",
                        "manifestEntryId": "agents.planner.agent.md",
                        "customization": {
                            "requiresInstalled": True,
                            "tokenNamespace": "agent:planner",
                            "questions": [
                                {
                                    "id": "plan-format",
                                    "answerKey": "agent.planner.planFormat",
                                    "kind": "choice",
                                    "options": ["full-phased", "tight-phased"],
                                }
                            ],
                        },
                    },
                    {
                        "id": "explore",
                        "status": "active",
                        "manifestEntryId": "agents.explore.agent.md",
                        "customization": {
                            "requiresInstalled": True,
                            "tokenNamespace": "agent:explore",
                            "questions": [
                                {
                                    "id": "output-style",
                                    "answerKey": "agent.explore.outputStyle",
                                    "kind": "choice",
                                    "options": ["concise-results", "context-rich"],
                                }
                            ],
                        },
                    },
                    {
                        "id": "review",
                        "status": "active",
                        "manifestEntryId": "agents.review.agent.md",
                        "customization": {
                            "requiresInstalled": True,
                            "tokenNamespace": "agent:review",
                            "questions": [
                                {
                                    "id": "reporting-threshold",
                                    "answerKey": "agent.review.reportingThreshold",
                                    "kind": "choice",
                                    "options": ["advisory-and-up", "medium-and-up"],
                                }
                            ],
                        },
                    }
                ]
            },
        }

        questions = _interview.build_interview_questions(policy, metadata, "setup")
        question_ids = {question["id"] for question in questions}
        self.assertIn("setup.depth", question_ids)
        self.assertIn("profile.selected", question_ids)
        self.assertIn("packs.selected", question_ids)
        self.assertIn("ownership.agents", question_ids)

        expanded_questions = _interview.expand_interview_questions(
            policy,
            metadata,
            {
                "managedFiles": [
                    {"id": "agents.commit.agent.md", "surface": "agents", "ownership": ["local", "plugin-backed-copilot-format"], "requiredWhen": []},
                    {"id": "agents.docs.agent.md", "surface": "agents", "ownership": ["local", "plugin-backed-copilot-format"], "requiredWhen": []},
                    {"id": "agents.planner.agent.md", "surface": "agents", "ownership": ["local", "plugin-backed-copilot-format"], "requiredWhen": []},
                    {"id": "agents.explore.agent.md", "surface": "agents", "ownership": ["local", "plugin-backed-copilot-format"], "requiredWhen": []},
                    {"id": "agents.review.agent.md", "surface": "agents", "ownership": ["local", "plugin-backed-copilot-format"], "requiredWhen": []},
                ]
            },
            "setup",
            {},
        )
        expanded_ids = {question["id"] for question in expanded_questions}
        self.assertIn("agent.commit.messageStyle", expanded_ids)
        self.assertIn("agent.commit.secretGuardMode", expanded_ids)
        self.assertIn("agent.docs.outputStyle", expanded_ids)
        self.assertIn("agent.planner.planFormat", expanded_ids)
        self.assertIn("agent.explore.outputStyle", expanded_ids)
        self.assertIn("agent.review.reportingThreshold", expanded_ids)

        plugin_backed_questions = _interview.expand_interview_questions(
            {**policy, "ownershipDefaults": {"agents": "plugin-backed-copilot-format", "skills": "plugin-backed-copilot-format"}},
            metadata,
            {
                "managedFiles": [
                    {"id": "agents.commit.agent.md", "surface": "agents", "ownership": ["local", "plugin-backed-copilot-format"], "requiredWhen": []},
                    {"id": "agents.docs.agent.md", "surface": "agents", "ownership": ["local", "plugin-backed-copilot-format"], "requiredWhen": []},
                    {"id": "agents.planner.agent.md", "surface": "agents", "ownership": ["local", "plugin-backed-copilot-format"], "requiredWhen": []},
                    {"id": "agents.explore.agent.md", "surface": "agents", "ownership": ["local", "plugin-backed-copilot-format"], "requiredWhen": []},
                    {"id": "agents.review.agent.md", "surface": "agents", "ownership": ["local", "plugin-backed-copilot-format"], "requiredWhen": []},
                ]
            },
            "setup",
            {"ownership.agents": "plugin-backed-copilot-format"},
            {},
        )
        plugin_backed_ids = {question["id"] for question in plugin_backed_questions}
        self.assertNotIn("agent.commit.messageStyle", plugin_backed_ids)
        self.assertNotIn("agent.commit.secretGuardMode", plugin_backed_ids)
        self.assertNotIn("agent.docs.outputStyle", plugin_backed_ids)
        self.assertNotIn("agent.planner.planFormat", plugin_backed_ids)
        self.assertNotIn("agent.explore.outputStyle", plugin_backed_ids)
        self.assertNotIn("agent.review.reportingThreshold", plugin_backed_ids)

        with tempfile.TemporaryDirectory() as tmpdir, mock.patch(
            "scripts.lifecycle._xanad._interview.collect_context",
            return_value=self._interview_context(policy, metadata),
        ), mock.patch(
            "scripts.lifecycle._xanad._interview.scan_existing_copilot_files",
            return_value=[".github/copilot-instructions.md"],
        ), mock.patch(
            "scripts.lifecycle._xanad._interview.scan_consumer_kept_updates",
            return_value=[".github/prompts/custom.prompt.md"],
        ), mock.patch(
            "scripts.lifecycle._xanad._interview.build_source_summary",
            return_value={"kind": "package-root"},
        ):
            workspace = Path(tmpdir)
            package_root = Path(tmpdir)
            setup_payload = _interview.build_interview_result(workspace, package_root, "setup")
            update_payload = _interview.build_interview_result(workspace, package_root, "update")
            repair_payload = _interview.build_interview_result(workspace, package_root, "repair")

        self.assertEqual(setup_payload["result"]["existingFiles"], [".github/copilot-instructions.md"])
        self.assertEqual(update_payload["result"]["existingFiles"], [".github/prompts/custom.prompt.md"])
        self.assertEqual(repair_payload["result"]["existingFiles"], [])
        self.assertIn(
            "agent.commit.messageStyle",
            {question["id"] for question in setup_payload["result"]["questions"]},
        )
        self.assertIn(
            "agent.commit.secretGuardMode",
            {question["id"] for question in setup_payload["result"]["questions"]},
        )
        self.assertIn(
            "agent.docs.outputStyle",
            {question["id"] for question in setup_payload["result"]["questions"]},
        )
        self.assertIn(
            "agent.planner.planFormat",
            {question["id"] for question in setup_payload["result"]["questions"]},
        )
        self.assertIn(
            "agent.explore.outputStyle",
            {question["id"] for question in setup_payload["result"]["questions"]},
        )
        self.assertIn(
            "agent.review.reportingThreshold",
            {question["id"] for question in setup_payload["result"]["questions"]},
        )

    def test_build_error_payload(self) -> None:
        payload, exit_code = _interview.build_error_payload(
            "plan",
            Path("/workspace"),
            Path("/package"),
            "contract_input_failure",
            "broken",
            4,
            mode="setup",
            details={"field": "x"},
        )

        self.assertEqual(exit_code, 4)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["errors"][0]["details"], {"field": "x"})

    def test_load_answers_returns_empty_mapping_without_path(self) -> None:
        self.assertEqual(_interview.load_answers(None), {})

    def test_load_answers_rejects_invalid_missing_and_non_object_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            invalid_path = Path(tmpdir) / "invalid.json"
            missing_path = Path(tmpdir) / "missing.json"
            list_path = Path(tmpdir) / "answers.json"
            invalid_path.write_text("{bad", encoding="utf-8")
            list_path.write_text("[]", encoding="utf-8")

            for path in (str(invalid_path), str(missing_path), str(list_path)):
                with self.subTest(path=path):
                    error = self._assert_load_answers_error(path)
                    self.assertEqual(error.code, "contract_input_failure")

    def test_validate_answer_value_rejects_invalid_choice_multi_choice_and_confirm(self) -> None:
        cases = [
            ({"id": "profile.selected", "kind": "choice", "options": ["balanced"]}, "invalid"),
            (
                {
                    "id": "packs.selected",
                    "kind": "multi-choice",
                    "options": ["tdd"],
                    "maxSelections": 1,
                },
                ["tdd", "docs"],
            ),
            ({"id": "mcp.enabled", "kind": "confirm"}, "yes"),
        ]

        for question, value in cases:
            with self.subTest(question=question["id"], value=value):
                with self.assertRaises(LifecycleCommandError):
                    _interview.validate_answer_value(question, value)

    def test_resolve_question_answers_uses_defaults_recommended_and_reports_unknown_ids(self) -> None:
        questions = [
            {"id": "setup.depth", "kind": "choice", "options": ["simple"], "default": "simple"},
            {"id": "profile.selected", "kind": "choice", "options": ["balanced"], "recommended": "balanced"},
            {"id": "ownership.skills", "kind": "choice", "options": ["local"], "required": True},
        ]

        resolved, unresolved, unknown_ids = _interview.resolve_question_answers(
            questions,
            {"extra.answer": True},
        )

        self.assertEqual(resolved["setup.depth"], "simple")
        self.assertEqual(resolved["profile.selected"], "balanced")
        self.assertEqual(unresolved, ["ownership.skills"])
        self.assertEqual(unknown_ids, ["extra.answer"])


if __name__ == "__main__":
    unittest.main()
