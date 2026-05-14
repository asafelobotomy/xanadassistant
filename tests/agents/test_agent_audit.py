"""Static audit tests for agent definition files."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "agents"
AGENTS_MD = REPO_ROOT / "AGENTS.md"

_READONLY_AGENTS = {"Debugger", "Planner", "Researcher", "Triage"}


def _parse_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter from an agent .md file. Stdlib only.

    Handles: scalar values, inline lists [a, b], block lists (- item),
    booleans (true/false), and hyphenated keys (argument-hint).
    """
    if not text.startswith("---"):
        return {}
    end = text.find("---", 3)
    if end == -1:
        return {}
    block = text[3:end]
    result: dict = {}
    lines = block.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        m = re.match(r"^([\w-]+):\s*(.*)", line)
        if not m:
            i += 1
            continue
        key, raw = m.group(1), m.group(2).strip()
        if raw.startswith("[") and raw.endswith("]"):
            inner = raw[1:-1]
            result[key] = [v.strip().strip("\"'") for v in inner.split(",") if v.strip()]
        elif raw == "":
            items: list[str] = []
            i += 1
            while i < len(lines) and lines[i].startswith("  - "):
                items.append(lines[i][4:].strip())
                i += 1
            result[key] = items
            continue
        elif raw.lower() == "true":
            result[key] = True
        elif raw.lower() == "false":
            result[key] = False
        else:
            result[key] = raw.strip("\"'")
        i += 1
    return result


class AgentAuditTests(unittest.TestCase):

    def _all_frontmatters(self) -> dict[str, dict]:
        return {
            path.name: _parse_frontmatter(path.read_text(encoding="utf-8"))
            for path in sorted(AGENTS_DIR.glob("*.agent.md"))
        }

    def test_all_agents_have_required_frontmatter_fields(self) -> None:
        required = {"name", "description", "argument-hint", "model", "tools", "user-invocable"}
        for filename, fm in self._all_frontmatters().items():
            missing = required - fm.keys()
            self.assertFalse(missing, f"{filename} missing fields: {missing}")

    def test_readonly_agents_lack_edit_permissions(self) -> None:
        for filename, fm in self._all_frontmatters().items():
            name = fm.get("name", "")
            if name in _READONLY_AGENTS:
                tools = fm.get("tools", [])
                self.assertNotIn(
                    "editFiles", tools,
                    f"{filename} ({name}) is read-only but lists editFiles",
                )

    def test_user_invocable_agents_have_argument_hints(self) -> None:
        for filename, fm in self._all_frontmatters().items():
            if fm.get("user-invocable") is True:
                hint = fm.get("argument-hint", "").strip()
                self.assertTrue(
                    hint,
                    f"{filename} is user-invocable but has empty argument-hint",
                )

    def test_all_agents_listed_in_agents_md(self) -> None:
        agents_md = AGENTS_MD.read_text(encoding="utf-8")
        for filename, fm in self._all_frontmatters().items():
            name = fm.get("name", "")
            self.assertIn(
                f"`{name}`", agents_md,
                f"{filename}: '{name}' not found in AGENTS.md routing table",
            )

    def test_delegation_targets_are_valid_agents(self) -> None:
        all_fm = self._all_frontmatters()
        known = {fm.get("name") for fm in all_fm.values()}
        for filename, fm in all_fm.items():
            for target in fm.get("agents", []):
                self.assertIn(
                    target, known,
                    f"{filename} delegates to unknown agent '{target}'",
                )

    def test_agent_names_are_unique(self) -> None:
        seen: set[str] = set()
        for filename, fm in self._all_frontmatters().items():
            name = fm.get("name", "")
            self.assertNotIn(name, seen, f"Duplicate agent name '{name}' in {filename}")
            seen.add(name)

    def test_descriptions_start_with_use_when(self) -> None:
        for filename, fm in self._all_frontmatters().items():
            desc = fm.get("description", "")
            self.assertTrue(
                desc.startswith("Use when:"),
                f"{filename}: description must start with 'Use when:' (got: {desc[:50]!r})",
            )


if __name__ == "__main__":
    unittest.main()
