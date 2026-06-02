from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout

from scripts.lifecycle._xanad._emit import emit_json_lines


class LifecycleEmitTests(unittest.TestCase):
    def _emit_events(self, payload: dict) -> tuple[list[dict], str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            emit_json_lines(payload)
        events = [json.loads(line) for line in stdout.getvalue().splitlines()]
        return events, stderr.getvalue()

    def test_emit_json_lines_uses_stdout_only_and_expected_event_order(self) -> None:
        payloads = {
            "inspect": {
                "command": "inspect",
                "status": "ok",
                "warnings": [],
                "result": {
                    "installState": "installed",
                    "manifestSummary": {"managed": 1},
                    "contracts": {"cli": True},
                },
            },
            "health-check": {
                "command": "health-check",
                "status": "drift",
                "warnings": [{"code": "warn", "message": "w", "details": {}}],
                "result": {"summary": {"missing": 1}, "unmanagedFiles": []},
            },
            "health-report": {
                "command": "health-report",
                "status": "ok",
                "warnings": [],
                "result": {
                    "check": {"status": "drift"},
                    "issueTitle": "[Health Check] xanadAssistant 0.3.6 — drift",
                    "issueLabels": ["health-check-report"],
                },
            },
            "interview": {
                "command": "interview",
                "status": "ok",
                "warnings": [],
                "result": {
                    "questions": [
                        {"id": "q1", "kind": "choice", "prompt": "Pick one", "required": True, "options": ["a"]}
                    ]
                },
            },
            "plan": {
                "command": "plan",
                "mode": "repair",
                "status": "approval-required",
                "warnings": [],
                "result": {
                    "installState": "installed",
                    "installPaths": {"legacyVersionFile": None, "lockfile": ".github/xanadAssistant-lock.json"},
                    "questions": [
                        {"id": "q1", "kind": "choice", "prompt": "Pick one", "required": True, "options": ["a"]}
                    ],
                    "approvalRequired": True,
                    "backupRequired": True,
                    "backupPlan": {"required": True},
                    "plannedLockfile": {"path": ".github/xanadAssistant-lock.json"},
                    "writes": {"add": 1},
                    "conflictSummary": {"count": 0},
                    "questionsResolved": True,
                    "conflictDetails": [],
                },
            },
            "apply": {
                "command": "apply",
                "status": "ok",
                "warnings": [],
                "result": {
                    "backup": {"created": False, "path": None},
                    "writes": {"added": 1},
                    "retired": [],
                    "sanitized": [],
                    "lockfile": {"written": True, "path": ".github/xanadAssistant-lock.json"},
                    "summary": {"written": True, "path": ".github/copilot-version.md"},
                    "validation": {"status": "passed"},
                },
            },
            "setup": {
                "command": "setup",
                "status": "ok",
                "warnings": [],
                "result": {
                    "backup": {"created": False, "path": None},
                    "writes": {"added": 1},
                    "retired": [],
                    "sanitized": [],
                    "lockfile": {"written": True, "path": ".github/xanadAssistant-lock.json"},
                    "summary": {"written": True, "path": ".github/copilot-version.md"},
                    "validation": {"status": "passed"},
                },
            },
        }
        expected_types = {
            "inspect": ["phase", "inspect-summary", "receipt"],
            "health-check": ["phase", "warning", "check-summary", "receipt"],
            "health-report": ["phase", "health-report-summary", "receipt"],
            "interview": ["phase", "question", "receipt"],
            "plan": ["phase", "inspect-summary", "question", "phase", "plan-summary", "receipt"],
            "apply": ["phase", "apply-report", "receipt"],
            "setup": ["phase", "apply-report", "receipt"],
        }

        for command, payload in payloads.items():
            with self.subTest(command=command):
                events, stderr = self._emit_events(payload)
                self.assertEqual(stderr, "")
                self.assertEqual([event["type"] for event in events], expected_types[command])
                self.assertEqual([event["sequence"] for event in events], list(range(1, len(events) + 1)))

    def test_emit_json_lines_emits_error_event_for_unknown_command(self) -> None:
        events, stderr = self._emit_events(
            {
                "command": "unknown",
                "warnings": [],
                "errors": [{"message": "unsupported command", "details": {"command": "unknown"}}],
            }
        )

        self.assertEqual(stderr, "")
        self.assertEqual([event["type"] for event in events], ["error"])
        self.assertEqual(events[0]["code"], "not_implemented")
        self.assertEqual(events[0]["message"], "unsupported command")

    def test_apply_report_event_includes_sanitized_field(self) -> None:
        sanitized_record = {"target": ".github/old.agent.md", "action": "archived", "archivePath": ".xanad-archive/20260101T000000/.github/old.agent.md"}
        payload = {
            "command": "repair",
            "status": "ok",
            "warnings": [],
            "result": {
                "backup": {"created": False, "path": None},
                "writes": {"added": 0, "unmanagedArchived": 1},
                "retired": [],
                "sanitized": [sanitized_record],
                "lockfile": {"written": True, "path": ".github/xanadAssistant-lock.json"},
                "summary": {"written": True, "path": ".github/copilot-version.md"},
                "validation": {"status": "passed"},
            },
        }

        events, stderr = self._emit_events(payload)

        self.assertEqual(stderr, "")
        apply_report = next(e for e in events if e["type"] == "apply-report")
        self.assertIn("sanitized", apply_report)
        self.assertEqual(apply_report["sanitized"], [sanitized_record])


if __name__ == "__main__":
    unittest.main()
