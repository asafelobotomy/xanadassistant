from __future__ import annotations

import unittest

from scripts.lifecycle._xanad import _interview_questions as interview_questions


class InterviewQuestionsTests(unittest.TestCase):
    def test_mcp_question_discloses_memory_server_and_persistence(self) -> None:
        question = interview_questions.mcp_question()
        reason = question["reason"]

        self.assertIn("memoryMcp.py", reason)
        self.assertIn("persistent SQLite-backed agent memory", reason)
        self.assertIn(".github/xanadAssistant/memory", reason)

    def test_optional_mcp_servers_describes_sqlite_as_read_only_workspace_local(self) -> None:
        question = interview_questions.mcp_servers_question()
        sqlite_option = next(option for option in question["options"] if option["id"] == "sqlite")

        self.assertIn("workspace-local", sqlite_option["description"])
        self.assertIn("read-only", sqlite_option["description"])

    def test_mcp_question_discloses_devdocs_and_filesystem_in_always_on_list(self) -> None:
        question = interview_questions.mcp_question()
        reason = question["reason"]

        self.assertIn("devDocsMcp.py", reason)
        self.assertIn("fsMcp.py", reason)

    def test_mcp_servers_reason_lists_all_always_on_servers(self) -> None:
        question = interview_questions.mcp_servers_question()
        reason = question["reason"]

        for server in ("xanadTools", "git", "web", "devDocs", "time", "memory", "security", "filesystem", "sequential-thinking"):
            self.assertIn(server, reason, f"\"{server}\" must appear in mcp.servers reason text")


if __name__ == "__main__":
    unittest.main()
