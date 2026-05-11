"""Tests for CLI parser and emit_json in the lifecycle engine."""
from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts.lifecycle._xanad._errors import _State
from scripts.lifecycle._xanad._main import main
from scripts.lifecycle._xanad._cli import add_common_arguments, build_parser
from scripts.lifecycle._xanad._emit import emit_json, emit_json_lines
from scripts.lifecycle._xanad._progress import (
    _ansi,
    _color_enabled,
    build_not_implemented_payload,
    emit_agent_progress,
    emit_payload,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


class CliParserTests(unittest.TestCase):
    def test_build_parser_returns_parser(self) -> None:
        import argparse
        parser = build_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)

    def test_inspect_subcommand_parses(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "inspect",
            "--workspace", "/tmp/ws",
            "--package-root", "/tmp/pkg",
        ])
        self.assertEqual("inspect", args.command)
        self.assertEqual("/tmp/ws", args.workspace)

    def test_check_subcommand_parses(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "check",
            "--workspace", "/tmp/ws",
            "--package-root", "/tmp/pkg",
        ])
        self.assertEqual("check", args.command)

    def test_interview_subcommand_parses_mode(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "interview",
            "--workspace", "/tmp/ws",
            "--package-root", "/tmp/pkg",
            "--mode", "update",
        ])
        self.assertEqual("interview", args.command)
        self.assertEqual("update", args.mode)

    def test_plan_setup_subcommand_parses(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "plan", "setup",
            "--workspace", "/tmp/ws",
            "--package-root", "/tmp/pkg",
        ])
        self.assertEqual("plan", args.command)
        self.assertEqual("setup", args.mode)

    def test_apply_subcommand_parses(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "apply",
            "--workspace", "/tmp/ws",
            "--package-root", "/tmp/pkg",
            "--non-interactive",
        ])
        self.assertEqual("apply", args.command)
        self.assertTrue(args.non_interactive)

    def test_common_flags_available_on_all_subparsers(self) -> None:
        parser = build_parser()
        for command in ("inspect", "check"):
            args = parser.parse_args([
                command,
                "--workspace", "/tmp/ws",
                "--package-root", "/tmp/pkg",
                "--json",
                "--json-lines",
                "--dry-run",
                "--ui", "agent",
            ])
            self.assertTrue(args.json)
            self.assertTrue(args.json_lines)
            self.assertTrue(args.dry_run)
            self.assertEqual("agent", args.ui)


class EmitJsonTests(unittest.TestCase):
    def test_emit_json_writes_to_stdout(self) -> None:
        payload = {"command": "inspect", "status": "ok", "test": True}
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            emit_json(payload)
        output = buf.getvalue()
        self.assertTrue(output.endswith("\n"))
        parsed = json.loads(output)
        self.assertTrue(parsed["test"])

    def test_emit_json_uses_indent(self) -> None:
        payload = {"a": {"b": 1}}
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            emit_json(payload)
        self.assertIn("  ", buf.getvalue())



if __name__ == "__main__":  # pragma: no cover
    unittest.main()
