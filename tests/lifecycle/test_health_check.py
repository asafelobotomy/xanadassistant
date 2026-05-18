from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.lifecycle._xanad._health_check import (
    HEALTH_CHECK_SCHEMA_VERSION,
    build_health_check_report,
    build_health_check_result,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PKG_ROOT = _REPO_ROOT


def _mock_context(install_state: str = "installed") -> dict:
    return {
        "installState": install_state,
        "lockfileState": {
            "data": {
                "package": {"version": "0.2.0"},
                "installMetadata": {
                    "profile": "balanced",
                    "packs": ["tdd"],
                    "mcpEnabled": True,
                },
                "timestamps": {
                    "appliedAt": "2026-01-01T00:00:00Z",
                    "updatedAt": "2026-01-02T00:00:00Z",
                },
                "manifest": {"hash": "sha256:abc123"},
                "resolvedTokenConflicts": {},
                "consumerResolutions": {".github/agents/custom.agent.md": "keep"},
            }
        },
        "manifest": {"packageVersion": "0.2.0"},
    }


def _mock_check_result(status: str = "clean") -> dict:
    entries = [{"surface": "agents", "target": ".github/agents/cleaner.agent.md", "status": "clean"}]
    if status != "clean":
        entries.append({"surface": "skills", "target": ".github/skills/ciPreflight/SKILL.md", "status": "stale"})
    return {
        "command": "check",
        "status": status,
        "warnings": [],
        "errors": [],
        "result": {
            "summary": {"clean": 10 if status == "clean" else 9, "stale": 0 if status == "clean" else 1, "missing": 0},
            "entries": entries,
        },
    }


def _mock_source_summary(kind: str = "github") -> dict:
    if kind == "package-root":
        return {"kind": "package-root", "source": "/home/user/xanadassistant"}
    return {"kind": "github", "source": "github:asafelobotomy/xanadassistant@v0.2.0"}


def _patch_all(context: dict | None = None, check: dict | None = None, source: dict | None = None):
    context = context or _mock_context()
    check = check or _mock_check_result()
    source = source or _mock_source_summary()
    return mock.patch.multiple(
        "scripts.lifecycle._xanad._health_check",
        collect_context=mock.MagicMock(return_value=context),
        build_check_result=mock.MagicMock(return_value=check),
        build_source_summary=mock.MagicMock(return_value=source),
    )


class HealthCheckReportFieldsTests(unittest.TestCase):
    def test_build_health_check_report_returns_required_top_level_keys(self) -> None:
        with _patch_all():
            report = build_health_check_report(Path("."), _PKG_ROOT)

        for key in ("healthCheckSchemaVersion", "generatedAt", "package", "install", "check", "system",
                    "issueTitle", "issueBody", "issueLabels"):
            with self.subTest(key=key):
                self.assertIn(key, report)

    def test_build_health_check_report_schema_version_matches_constant(self) -> None:
        with _patch_all():
            report = build_health_check_report(Path("."), _PKG_ROOT)
        self.assertEqual(report["healthCheckSchemaVersion"], HEALTH_CHECK_SCHEMA_VERSION)

    def test_build_health_check_report_includes_package_version(self) -> None:
        with _patch_all():
            report = build_health_check_report(Path("."), _PKG_ROOT)
        self.assertEqual(report["package"]["version"], "0.2.0")

    def test_build_health_check_report_includes_install_metadata(self) -> None:
        with _patch_all():
            report = build_health_check_report(Path("."), _PKG_ROOT)
        install = report["install"]
        self.assertEqual(install["profile"], "balanced")
        self.assertEqual(install["packs"], ["tdd"])
        self.assertTrue(install["mcpEnabled"])
        self.assertEqual(install["manifestHash"], "sha256:abc123")

    def test_build_health_check_report_includes_check_status(self) -> None:
        with _patch_all():
            report = build_health_check_report(Path("."), _PKG_ROOT)
        self.assertEqual(report["check"]["status"], "clean")

    def test_build_health_check_report_includes_system_info(self) -> None:
        with _patch_all():
            report = build_health_check_report(Path("."), _PKG_ROOT)
        system = report["system"]
        self.assertIn("platform", system)
        self.assertIn("python", system)
        major_minor = f"{sys.version_info.major}.{sys.version_info.minor}"
        self.assertEqual(system["python"], major_minor)

    def test_build_health_check_report_preserves_optional_label(self) -> None:
        with _patch_all():
            report = build_health_check_report(Path("."), _PKG_ROOT, label="my-project")
        self.assertEqual(report["label"], "my-project")

    def test_build_health_check_report_label_none_by_default(self) -> None:
        with _patch_all():
            report = build_health_check_report(Path("."), _PKG_ROOT)
        self.assertIsNone(report["label"])

    def test_build_health_check_report_issue_labels_contains_health_check_report(self) -> None:
        with _patch_all():
            report = build_health_check_report(Path("."), _PKG_ROOT)
        self.assertIn("health-check-report", report["issueLabels"])


class HealthCheckSourceSanitizationTests(unittest.TestCase):
    def test_local_package_root_source_is_redacted(self) -> None:
        source = _mock_source_summary(kind="package-root")
        with _patch_all(source=source):
            report = build_health_check_report(Path("."), _PKG_ROOT)
        self.assertEqual(report["package"]["source"], "local")
        self.assertNotIn("/home", report["package"]["source"])

    def test_github_source_is_preserved(self) -> None:
        source = _mock_source_summary(kind="github")
        with _patch_all(source=source):
            report = build_health_check_report(Path("."), _PKG_ROOT)
        self.assertTrue(report["package"]["source"].startswith("github:"))

    def test_consumer_resolution_count_not_paths(self) -> None:
        with _patch_all():
            report = build_health_check_report(Path("."), _PKG_ROOT)
        # consumerResolutionCount is a count, not a list of paths
        self.assertIsInstance(report["install"]["consumerResolutionCount"], int)
        self.assertNotIn("consumerResolutions", report["install"])


class HealthCheckWarningsTests(unittest.TestCase):
    def test_check_warnings_are_codes_only(self) -> None:
        check = _mock_check_result()
        check["warnings"] = [
            {"code": "package_version_changed", "message": "Sensitive workspace path /home/user/..."},
        ]
        with _patch_all(check=check):
            report = build_health_check_report(Path("."), _PKG_ROOT)
        warnings = report["check"]["warnings"]
        self.assertIn("package_version_changed", warnings)
        # Messages must not appear in the structured warnings list
        self.assertNotIn("Sensitive workspace path /home/user/...", str(warnings))


class HealthCheckIssueTitleTests(unittest.TestCase):
    def test_issue_title_includes_version_and_status(self) -> None:
        with _patch_all():
            report = build_health_check_report(Path("."), _PKG_ROOT)
        title = report["issueTitle"]
        self.assertIn("0.2.0", title)
        self.assertIn("clean", title)
        self.assertTrue(title.startswith("[Health Check]"))


class HealthCheckIssueBodyTests(unittest.TestCase):
    def test_issue_body_includes_all_sections(self) -> None:
        with _patch_all():
            report = build_health_check_report(Path("."), _PKG_ROOT)
        body = report["issueBody"]
        for section in ("Package", "Install State", "Check", "System", "Health Check Metadata"):
            with self.subTest(section=section):
                self.assertIn(section, body)

    def test_issue_body_includes_drift_details_when_stale(self) -> None:
        check = _mock_check_result(status="drift")
        check["result"]["entries"] = [
            {"surface": "skills", "target": ".github/skills/ciPreflight/SKILL.md", "status": "stale"},
        ]
        check["result"]["summary"] = {"clean": 9, "stale": 1, "missing": 0}
        with _patch_all(check=check):
            report = build_health_check_report(Path("."), _PKG_ROOT)
        self.assertIn("Drift Details", report["issueBody"])
        self.assertIn(".github/skills/ciPreflight/SKILL.md", report["issueBody"])

    def test_issue_body_has_no_drift_section_when_clean(self) -> None:
        with _patch_all():
            report = build_health_check_report(Path("."), _PKG_ROOT)
        self.assertNotIn("Drift Details", report["issueBody"])

    def test_issue_body_includes_label_when_provided(self) -> None:
        with _patch_all():
            report = build_health_check_report(Path("."), _PKG_ROOT, label="acme-corp")
        self.assertIn("acme-corp", report["issueBody"])


class HealthCheckResultPayloadTests(unittest.TestCase):
    def test_build_health_check_result_returns_command_field(self) -> None:
        with _patch_all():
            payload = build_health_check_result(Path("."), _PKG_ROOT)
        self.assertEqual(payload["command"], "health-check")

    def test_build_health_check_result_status_is_ok(self) -> None:
        with _patch_all():
            payload = build_health_check_result(Path("."), _PKG_ROOT)
        self.assertEqual(payload["status"], "ok")

    def test_build_health_check_result_result_contains_health_check_report(self) -> None:
        with _patch_all():
            payload = build_health_check_result(Path("."), _PKG_ROOT)
        self.assertIn("healthCheckSchemaVersion", payload["result"])


class HealthCheckCLIIntegrationTests(unittest.TestCase):
    """Verify the health-check subcommand is reachable via the CLI."""

    def test_health_check_subcommand_help_exits_cleanly(self) -> None:
        result = subprocess.run(
            [sys.executable, "xanadAssistant.py", "health-check", "--help"],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("--label", result.stdout)

    def test_health_check_subcommand_requires_workspace(self) -> None:
        result = subprocess.run(
            [sys.executable, "xanadAssistant.py", "health-check"],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
        )
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
