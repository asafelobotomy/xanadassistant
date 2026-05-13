from __future__ import annotations


def personalisation_questions() -> list[dict]:
    """Return the static Tier 2/3 personalisation questions.

    These are appended to the interview after the core ownership questions.
    The options use the {id, label, description} form; answer values must match an option id.
    """
    return [
        {
            "id": "response.style",
            "kind": "choice",
            "batch": "advanced",
            "prompt": "What response style do you prefer?",
            "required": False,
            "default": "balanced",
            "recommended": "balanced",
            "options": [
                {"id": "concise", "label": "Concise", "description": "Code with minimal prose"},
                {"id": "balanced", "label": "Balanced", "description": "Code with brief explanation"},
                {"id": "verbose", "label": "Verbose", "description": "Code with full step-by-step explanation"},
            ],
        },
        {
            "id": "autonomy.level",
            "kind": "choice",
            "batch": "advanced",
            "prompt": "How should the assistant handle ambiguity?",
            "required": False,
            "default": "ask-first",
            "recommended": "ask-first",
            "options": [
                {"id": "ask-first", "label": "Ask first", "description": "Always confirm before acting"},
                {"id": "act-then-tell", "label": "Act then tell", "description": "Make a reasonable choice and explain it"},
                {"id": "best-judgement", "label": "Best judgement", "description": "Act silently on low-risk choices"},
            ],
        },
        {
            "id": "agent.persona",
            "kind": "choice",
            "batch": "advanced",
            "prompt": "What tone should the assistant use?",
            "required": False,
            "default": "professional",
            "recommended": "professional",
            "options": [
                {"id": "professional", "label": "Professional", "description": "Concise, neutral, precise"},
                {"id": "mentor", "label": "Mentor", "description": "Patient, explanatory, teaching-focused"},
                {"id": "pair-programmer", "label": "Pair programmer", "description": "Collaborative, iterative, direct"},
                {"id": "direct", "label": "Direct", "description": "Minimal chat, maximum output"},
            ],
        },
        {
            "id": "testing.philosophy",
            "kind": "choice",
            "batch": "full",
            "prompt": "What is your testing philosophy?",
            "required": False,
            "default": "always",
            "recommended": "always",
            "options": [
                {"id": "always", "label": "Always", "description": "Write tests alongside every code change"},
                {"id": "suggest", "label": "Suggest", "description": "Propose tests but do not block on them"},
                {"id": "skip", "label": "Skip", "description": "Do not write or suggest tests unless asked"},
            ],
        },
    ]


def mcp_servers_question() -> dict:
    """Return the optional MCP server selection question."""
    return {
        "id": "mcp.servers",
        "kind": "multi-choice",
        "batch": "full",
        "prompt": "Which optional MCP servers would you like to enable?",
        "required": False,
        "options": [
            {
                "id": "github",
                "label": "GitHub",
                "description": (
                    "Issues, PRs, Actions, code search, file contents via REST API. "
                    "Requires GITHUB_TOKEN environment variable."
                ),
            },
            {
                "id": "sqlite",
                "label": "SQLite",
                "description": "Query and inspect local SQLite databases (read-only by default).",
            },
        ],
        "recommended": [],
        "default": [],
        "reason": (
            "The git, web, time, and security servers are always enabled when MCP is on. "
            "GitHub (requires GITHUB_TOKEN) and SQLite (workspace-specific) ship disabled "
            "by default in .vscode/mcp.json. Select them here to enable, or toggle the "
            '"disabled" flag directly in .vscode/mcp.json at any time.'
        ),
        "requiredFor": [],
    }


def mcp_question() -> dict:
    """Return the static mcp.enabled confirm question."""
    return {
        "id": "mcp.enabled",
        "kind": "confirm",
        "batch": "simple",
        "prompt": "Enable MCP configuration for this workspace?",
        "required": True,
        "default": True,
        "recommended": True,
        "reason": (
            "Enabling MCP installs all hook scripts and .vscode/mcp.json atomically. "
            "Always-on servers: xanadWorkspaceMcp.py (lifecycle), gitMcp.py (git), "
            "webMcp.py (search + fetch), timeMcp.py (time/duration), "
            "securityMcp.py (OSV + deps.dev), mcpSequentialThinkingServer.py (reasoning). "
            "Optional servers (disabled by default): githubMcp.py (GitHub REST API, requires GITHUB_TOKEN), "
            "sqliteMcp.py (local SQLite databases). "
            "Outbound access is governed by each server at call time."
        ),
        "requiredFor": ["mcp-config"],
    }
