from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.lifecycle._xanad import _conditions


class AgentTokenRenderingTests(unittest.TestCase):
    def test_resolve_token_values_supports_render_values_that_reference_pack_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "packs" / "core").mkdir(parents=True)
            (root / "packs" / "core" / "tokens.json").write_text(
                json.dumps(
                    {
                        "pack:commit-style": "Pack commit guidance.",
                        "pack:secret-guard": "Pack secret guidance.",
                    }
                ),
                encoding="utf-8",
            )
            workspace = root / "workspace"
            workspace.mkdir()

            explicit_values = _conditions.resolve_token_values(
                {
                    "tokenRules": [
                        {"token": "{{agent:commit:message-style}}"},
                        {"token": "{{agent:commit:secret-guard}}"},
                    ]
                },
                workspace,
                {
                    "agent.commit.messageStyle": "conventional-with-context",
                    "agent.commit.secretGuardMode": "surface-and-stop",
                },
                package_root=root,
                metadata={
                    "agentRegistry": {
                        "agents": [
                            {
                                "id": "commit",
                                "status": "active",
                                "customization": {
                                    "tokenNamespace": "agent:commit",
                                    "questions": [
                                        {
                                            "answerKey": "agent.commit.messageStyle",
                                            "tokens": ["{{agent:commit:message-style}}"],
                                            "fallbackToken": "{{pack:commit-style}}",
                                            "render": {
                                                "conventional-with-context": "{{pack:commit-style}}"
                                            },
                                        },
                                        {
                                            "answerKey": "agent.commit.secretGuardMode",
                                            "tokens": ["{{agent:commit:secret-guard}}"],
                                            "fallbackToken": "{{pack:secret-guard}}",
                                            "render": {
                                                "surface-and-stop": "{{pack:secret-guard}}"
                                            },
                                        },
                                    ],
                                },
                            }
                        ]
                    }
                },
            )

        self.assertEqual(explicit_values["{{agent:commit:message-style}}"], "Pack commit guidance.")
        self.assertEqual(explicit_values["{{agent:commit:secret-guard}}"], "Pack secret guidance.")

    def test_resolve_token_values_renders_agent_tokens_and_falls_back_to_pack_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "packs" / "core").mkdir(parents=True)
            (root / "packs" / "core" / "tokens.json").write_text(
                json.dumps(
                    {
                        "pack:commit-style": "Write commit messages following Conventional Commits 1.0.",
                        "pack:secret-guard": "Before staging or committing, check for hardcoded credentials and surface any probable secret before proceeding.",
                        "pack:review-depth": "By default, report all findings at Advisory and above.",
                        "pack:output-style": "Provide thorough responses with context and explanation.",
                        "pack:plan-format": "Produce full step-by-step plans with assumptions and risks.",
                    }
                ),
                encoding="utf-8",
            )
            workspace = root / "workspace"
            workspace.mkdir()

            fallback_values = _conditions.resolve_token_values(
                {
                    "tokenRules": [
                        {"token": "{{agent:commit:message-style}}"},
                        {"token": "{{agent:commit:secret-guard}}"},
                        {"token": "{{agent:review:reporting-threshold}}"},
                        {"token": "{{agent:docs:output-style}}"},
                        {"token": "{{agent:planner:plan-format}}"},
                        {"token": "{{agent:explore:output-style}}"},
                    ]
                },
                workspace,
                {},
                package_root=root,
                metadata={
                    "agentRegistry": {
                        "agents": [
                            {
                                "id": "commit",
                                "status": "active",
                                "customization": {
                                    "tokenNamespace": "agent:commit",
                                    "questions": [
                                        {
                                            "answerKey": "agent.commit.messageStyle",
                                            "tokens": ["{{agent:commit:message-style}}"],
                                            "fallbackToken": "{{pack:commit-style}}",
                                            "render": {
                                                "conventional-subject-first": "Write commit messages using Conventional Commits 1.0 with a precise subject line first."
                                            },
                                        },
                                        {
                                            "answerKey": "agent.commit.secretGuardMode",
                                            "tokens": ["{{agent:commit:secret-guard}}"],
                                            "fallbackToken": "{{pack:secret-guard}}",
                                            "render": {
                                                "refuse-on-probable-secret": "If any probable secret is found, stop the workflow and refuse to proceed until it is removed."
                                            },
                                        },
                                    ],
                                },
                            },
                            {
                                "id": "docs",
                                "status": "active",
                                "customization": {
                                    "tokenNamespace": "agent:docs",
                                    "questions": [
                                        {
                                            "answerKey": "agent.docs.outputStyle",
                                            "tokens": ["{{agent:docs:output-style}}"],
                                            "fallbackToken": "{{pack:output-style}}",
                                            "render": {
                                                "concise-guides": "Use compact Markdown sections with short headings."
                                            },
                                        }
                                    ],
                                },
                            },
                            {
                                "id": "planner",
                                "status": "active",
                                "customization": {
                                    "tokenNamespace": "agent:planner",
                                    "questions": [
                                        {
                                            "answerKey": "agent.planner.planFormat",
                                            "tokens": ["{{agent:planner:plan-format}}"],
                                            "fallbackToken": "{{pack:plan-format}}",
                                            "render": {
                                                "tight-phased": "Structure plans as short numbered phases."
                                            },
                                        }
                                    ],
                                },
                            },
                            {
                                "id": "explore",
                                "status": "active",
                                "customization": {
                                    "tokenNamespace": "agent:explore",
                                    "questions": [
                                        {
                                            "answerKey": "agent.explore.outputStyle",
                                            "tokens": ["{{agent:explore:output-style}}"],
                                            "fallbackToken": "{{pack:output-style}}",
                                            "render": {
                                                "concise-results": "Report files found with workspace-relative paths and line numbers."
                                            },
                                        }
                                    ],
                                },
                            },
                            {
                                "id": "review",
                                "status": "active",
                                "customization": {
                                    "tokenNamespace": "agent:review",
                                    "questions": [
                                        {
                                            "answerKey": "agent.review.reportingThreshold",
                                            "tokens": ["{{agent:review:reporting-threshold}}"],
                                            "fallbackToken": "{{pack:review-depth}}",
                                            "render": {
                                                "medium-and-up": "By default, report Medium severity and above."
                                            },
                                        }
                                    ],
                                },
                            }
                        ]
                    }
                },
            )
            explicit_values = _conditions.resolve_token_values(
                {
                    "tokenRules": [
                        {"token": "{{agent:commit:message-style}}"},
                        {"token": "{{agent:commit:secret-guard}}"},
                        {"token": "{{agent:review:reporting-threshold}}"},
                        {"token": "{{agent:docs:output-style}}"},
                        {"token": "{{agent:planner:plan-format}}"},
                        {"token": "{{agent:explore:output-style}}"},
                    ]
                },
                workspace,
                {
                    "agent.commit.messageStyle": "conventional-subject-first",
                    "agent.commit.secretGuardMode": "refuse-on-probable-secret",
                    "agent.review.reportingThreshold": "medium-and-up",
                    "agent.docs.outputStyle": "concise-guides",
                    "agent.planner.planFormat": "tight-phased",
                    "agent.explore.outputStyle": "concise-results",
                },
                package_root=root,
                metadata={
                    "agentRegistry": {
                        "agents": [
                            {
                                "id": "commit",
                                "status": "active",
                                "customization": {
                                    "tokenNamespace": "agent:commit",
                                    "questions": [
                                        {
                                            "answerKey": "agent.commit.messageStyle",
                                            "tokens": ["{{agent:commit:message-style}}"],
                                            "fallbackToken": "{{pack:commit-style}}",
                                            "render": {
                                                "conventional-subject-first": "Write commit messages using Conventional Commits 1.0 with a precise subject line first."
                                            },
                                        },
                                        {
                                            "answerKey": "agent.commit.secretGuardMode",
                                            "tokens": ["{{agent:commit:secret-guard}}"],
                                            "fallbackToken": "{{pack:secret-guard}}",
                                            "render": {
                                                "refuse-on-probable-secret": "If any probable secret is found, stop the workflow and refuse to proceed until it is removed."
                                            },
                                        },
                                    ],
                                },
                            },
                            {
                                "id": "docs",
                                "status": "active",
                                "customization": {
                                    "tokenNamespace": "agent:docs",
                                    "questions": [
                                        {
                                            "answerKey": "agent.docs.outputStyle",
                                            "tokens": ["{{agent:docs:output-style}}"],
                                            "fallbackToken": "{{pack:output-style}}",
                                            "render": {
                                                "concise-guides": "Use compact Markdown sections with short headings."
                                            },
                                        }
                                    ],
                                },
                            },
                            {
                                "id": "planner",
                                "status": "active",
                                "customization": {
                                    "tokenNamespace": "agent:planner",
                                    "questions": [
                                        {
                                            "answerKey": "agent.planner.planFormat",
                                            "tokens": ["{{agent:planner:plan-format}}"],
                                            "fallbackToken": "{{pack:plan-format}}",
                                            "render": {
                                                "tight-phased": "Structure plans as short numbered phases."
                                            },
                                        }
                                    ],
                                },
                            },
                            {
                                "id": "explore",
                                "status": "active",
                                "customization": {
                                    "tokenNamespace": "agent:explore",
                                    "questions": [
                                        {
                                            "answerKey": "agent.explore.outputStyle",
                                            "tokens": ["{{agent:explore:output-style}}"],
                                            "fallbackToken": "{{pack:output-style}}",
                                            "render": {
                                                "concise-results": "Report files found with workspace-relative paths and line numbers."
                                            },
                                        }
                                    ],
                                },
                            },
                            {
                                "id": "review",
                                "status": "active",
                                "customization": {
                                    "tokenNamespace": "agent:review",
                                    "questions": [
                                        {
                                            "answerKey": "agent.review.reportingThreshold",
                                            "tokens": ["{{agent:review:reporting-threshold}}"],
                                            "fallbackToken": "{{pack:review-depth}}",
                                            "render": {
                                                "medium-and-up": "By default, report Medium severity and above."
                                            },
                                        }
                                    ],
                                },
                            }
                        ]
                    }
                },
            )

        self.assertEqual(
            fallback_values["{{agent:commit:message-style}}"],
            "Write commit messages following Conventional Commits 1.0.",
        )
        self.assertEqual(
            fallback_values["{{agent:commit:secret-guard}}"],
            "Before staging or committing, check for hardcoded credentials and surface any probable secret before proceeding.",
        )
        self.assertEqual(
            fallback_values["{{agent:review:reporting-threshold}}"],
            "By default, report all findings at Advisory and above.",
        )
        self.assertEqual(
            fallback_values["{{agent:docs:output-style}}"],
            "Provide thorough responses with context and explanation.",
        )
        self.assertEqual(
            fallback_values["{{agent:planner:plan-format}}"],
            "Produce full step-by-step plans with assumptions and risks.",
        )
        self.assertEqual(
            fallback_values["{{agent:explore:output-style}}"],
            "Provide thorough responses with context and explanation.",
        )
        self.assertEqual(
            explicit_values["{{agent:commit:message-style}}"],
            "Write commit messages using Conventional Commits 1.0 with a precise subject line first.",
        )
        self.assertEqual(
            explicit_values["{{agent:commit:secret-guard}}"],
            "If any probable secret is found, stop the workflow and refuse to proceed until it is removed.",
        )
        self.assertEqual(
            explicit_values["{{agent:review:reporting-threshold}}"],
            "By default, report Medium severity and above.",
        )
        self.assertEqual(
            explicit_values["{{agent:docs:output-style}}"],
            "Use compact Markdown sections with short headings.",
        )
        self.assertEqual(
            explicit_values["{{agent:planner:plan-format}}"],
            "Structure plans as short numbered phases.",
        )
        self.assertEqual(
            explicit_values["{{agent:explore:output-style}}"],
            "Report files found with workspace-relative paths and line numbers.",
        )



if __name__ == "__main__":
    unittest.main()
