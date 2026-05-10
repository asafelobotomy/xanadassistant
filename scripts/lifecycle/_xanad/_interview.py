from __future__ import annotations

import json
from pathlib import Path

from scripts.lifecycle._xanad._errors import LifecycleCommandError
from scripts.lifecycle._xanad._inspect import collect_context
from scripts.lifecycle._xanad._loader import load_json
from scripts.lifecycle._xanad._source import build_source_summary


def build_interview_questions(policy: dict, metadata: dict, mode: str) -> list[dict]:
    questions = []
    ownership_defaults = policy.get("ownershipDefaults", {})
    profile_registry = metadata.get("profileRegistry") or {}
    pack_registry = metadata.get("packRegistry") or {}

    profile_options = [profile["id"] for profile in profile_registry.get("profiles", [])]
    if profile_options:
        questions.append({
            "id": "profile.selected",
            "kind": "choice",
            "prompt": f"Which behavior profile should {mode} use?",
            "required": True,
            "options": profile_options,
            "recommended": "balanced" if "balanced" in profile_options else profile_options[0],
            "default": "balanced" if "balanced" in profile_options else profile_options[0],
            "requiredFor": ["profile"],
        })

    optional_packs = [pack["id"] for pack in pack_registry.get("packs", []) if pack.get("optional", False)]
    if optional_packs:
        questions.append({
            "id": "packs.selected",
            "kind": "multi-choice",
            "prompt": f"Which optional packs should {mode} consider?",
            "required": False,
            "options": optional_packs,
            "recommended": [],
            "default": [],
            "requiredFor": ["packs"],
        })

    for surface in ("agents", "skills"):
        if surface not in ownership_defaults:
            continue
        questions.append({
            "id": f"ownership.{surface}",
            "kind": "choice",
            "prompt": f"How should {surface} be owned for this workspace?",
            "required": True,
            "options": ["local", "plugin-backed-copilot-format"],
            "recommended": ownership_defaults[surface],
            "default": ownership_defaults[surface],
            "requiredFor": [surface],
        })

    if "mcp-config" in policy.get("canonicalSurfaces", []):
        questions.append({
            "id": "response.style",
            "kind": "choice",
            "prompt": "What response style do you prefer?",
            "required": False,
            "default": "balanced",
            "recommended": "balanced",
            "options": [
                {"id": "concise", "label": "Concise", "description": "Code with minimal prose"},
                {"id": "balanced", "label": "Balanced", "description": "Code with brief explanation"},
                {"id": "verbose", "label": "Verbose", "description": "Code with full step-by-step explanation"},
            ],
        })
        questions.append({
            "id": "autonomy.level",
            "kind": "choice",
            "prompt": "How should the assistant handle ambiguity?",
            "required": False,
            "default": "ask-first",
            "recommended": "ask-first",
            "options": [
                {"id": "ask-first", "label": "Ask first", "description": "Always confirm before acting"},
                {"id": "act-then-tell", "label": "Act then tell", "description": "Make a reasonable choice and explain it"},
                {"id": "best-judgement", "label": "Best judgement", "description": "Act silently on low-risk choices"},
            ],
        })
        questions.append({
            "id": "agent.persona",
            "kind": "choice",
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
        })
        questions.append({
            "id": "testing.philosophy",
            "kind": "choice",
            "prompt": "What is your testing philosophy?",
            "required": False,
            "default": "always",
            "recommended": "always",
            "options": [
                {"id": "always", "label": "Always", "description": "Write tests alongside every code change"},
                {"id": "suggest", "label": "Suggest", "description": "Propose tests but do not block on them"},
                {"id": "skip", "label": "Skip", "description": "Do not write or suggest tests unless asked"},
            ],
        })
        questions.append({
            "id": "mcp.enabled",
            "kind": "confirm",
            "prompt": "Enable MCP configuration for this workspace?",
            "required": True,
            "default": True,
            "recommended": True,
            "reason": (
                "Enabling MCP installs three files atomically: xanad-workspace-mcp.py (lifecycle tools), "
                "mcp-sequential-thinking-server.py (sequential-thinking tools), and .vscode/mcp.json "
                "(VS Code server registration). Outbound access is governed by each server, not by "
                "whether the workspace installs its local MCP configuration."
            ),
            "requiredFor": ["mcp-config"],
        })

    return questions


def build_interview_result(workspace: Path, package_root: Path, mode: str) -> dict:
    context = collect_context(workspace, package_root)
    questions = build_interview_questions(context["policy"], context["metadata"], mode)

    return {
        "command": "interview",
        "mode": mode,
        "workspace": str(workspace),
        "source": build_source_summary(package_root),
        "status": "ok",
        "warnings": context["warnings"],
        "errors": [],
        "result": {
            "installState": context["installState"],
            "discoveryMetadata": context["metadataArtifacts"],
            "questionCount": len(questions),
            "questions": questions,
        },
    }


def build_error_payload(
    command: str,
    workspace: Path,
    package_root: Path,
    code: str,
    message: str,
    exit_code: int,
    mode: str | None = None,
    details: dict | None = None,
) -> tuple[dict, int]:
    return (
        {
            "command": command,
            "mode": mode,
            "workspace": str(workspace),
            "source": build_source_summary(package_root),
            "status": "error",
            "warnings": [],
            "errors": [{"code": code, "message": message, "details": details or {}}],
            "result": {},
        },
        exit_code,
    )


def load_answers(path_value: str | None) -> dict:
    if path_value is None:
        return {}

    answers_path = Path(path_value).resolve()
    if not answers_path.exists():
        raise LifecycleCommandError(
            "contract_input_failure",
            "Answer file was not found.",
            4,
            {"path": str(answers_path)},
        )

    try:
        data = load_json(answers_path)
    except json.JSONDecodeError as error:
        raise LifecycleCommandError(
            "contract_input_failure",
            "Answer file is not valid JSON.",
            4,
            {"path": str(answers_path), "line": error.lineno, "column": error.colno},
        ) from error

    if not isinstance(data, dict):
        raise LifecycleCommandError(
            "contract_input_failure",
            "Answer file must contain a JSON object.",
            4,
            {"path": str(answers_path)},
        )
    return data


def validate_answer_value(question: dict, value: object) -> None:
    kind = question.get("kind")
    options = question.get("options", [])

    if kind == "choice":
        if not isinstance(value, str) or value not in options:
            raise LifecycleCommandError(
                "contract_input_failure",
                f"Invalid answer for {question['id']}.",
                4,
                {"questionId": question["id"], "expected": options, "received": value},
            )
        return

    if kind == "multi-choice":
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise LifecycleCommandError(
                "contract_input_failure",
                f"Invalid answer for {question['id']}.",
                4,
                {"questionId": question["id"], "expected": options, "received": value},
            )
        if any(item not in options for item in value):
            raise LifecycleCommandError(
                "contract_input_failure",
                f"Invalid answer for {question['id']}.",
                4,
                {"questionId": question["id"], "expected": options, "received": value},
            )
        return

    if kind == "confirm" and not isinstance(value, bool):
        raise LifecycleCommandError(
            "contract_input_failure",
            f"Invalid answer for {question['id']}.",
            4,
            {"questionId": question["id"], "expected": "boolean", "received": value},
        )


def resolve_question_answers(questions: list[dict], answers: dict) -> tuple[dict, list[str], list[str]]:
    resolved_answers: dict = {}
    unresolved: list[str] = []
    question_map = {question["id"]: question for question in questions}

    unknown_ids = sorted(answer_id for answer_id in answers if answer_id not in question_map)

    for question in questions:
        question_id = question["id"]
        if question_id in answers:
            validate_answer_value(question, answers[question_id])
            resolved_answers[question_id] = answers[question_id]
            continue
        if "default" in question:
            resolved_answers[question_id] = question["default"]
            continue
        if question.get("recommended") is not None:
            resolved_answers[question_id] = question["recommended"]
            continue
        if question.get("required"):
            unresolved.append(question_id)

    return resolved_answers, unresolved, unknown_ids
