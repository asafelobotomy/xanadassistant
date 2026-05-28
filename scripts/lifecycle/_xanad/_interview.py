from __future__ import annotations

import json
from pathlib import Path

from scripts.lifecycle._xanad._agent_customization import build_agent_customization_questions
from scripts.lifecycle._xanad._pack_customization import build_pack_customization_questions
from scripts.lifecycle._xanad._conditions import normalize_plan_answers
from scripts.lifecycle._xanad._errors import LifecycleCommandError
from scripts.lifecycle._xanad._inspect import collect_context
from scripts.lifecycle._xanad._interview_questions import mcp_question, mcp_servers_question, personalisation_questions, settings_questions
from scripts.lifecycle._xanad._loader import load_json
from scripts.lifecycle._xanad._plan_c import seed_answers_from_install_state, seed_answers_from_profile
from scripts.lifecycle._xanad._prescan import scan_consumer_kept_updates, scan_existing_copilot_files
from scripts.lifecycle._xanad._source import build_source_summary


def build_interview_questions(policy: dict, metadata: dict, mode: str) -> list[dict]:
    questions = []
    ownership_defaults = policy.get("ownershipDefaults", {})
    profile_registry = metadata.get("profileRegistry") or {}
    pack_registry = metadata.get("packRegistry") or {}

    # ── setup ────────────────────────────────────────────────────────────────
    questions.append({
        "id": "setup.depth",
        "kind": "choice",
        "batch": "setup",
        "prompt": "How much would you like to customise this install?",
        "required": True,
        "default": "simple",
        "recommended": "simple",
        "options": [
            {"id": "simple", "label": "Simple", "description": "Core install with sensible defaults — profile, packs, and MCP"},
            {"id": "advanced", "label": "Advanced", "description": "Adds ownership model, personalisation, and editor settings"},
            {"id": "full", "label": "Full", "description": "All options including testing philosophy and optional MCP servers"},
        ],
    })

    # ── simple ───────────────────────────────────────────────────────────────
    profile_options = [
        {"id": p["id"], "label": p["name"], "description": p["summary"]}
        for p in profile_registry.get("profiles", [])
        if p.get("status") == "active"
    ]
    if profile_options:
        profile_ids = [o["id"] for o in profile_options]
        default_profile = "balanced" if "balanced" in profile_ids else profile_ids[0]
        questions.append({
            "id": "profile.selected",
            "kind": "choice",
            "batch": "simple",
            "prompt": "Which behavior profile should this workspace use?",
            "required": True,
            "options": profile_options,
            "recommended": default_profile,
            "default": default_profile,
            "requiredFor": ["profile"],
        })

    optional_packs = [
        {"id": p["id"], "label": p["name"], "description": p["summary"]}
        for p in pack_registry.get("packs", [])
        if p.get("optional", False) and p.get("status") == "active"
    ]
    if optional_packs:
        questions.append({
            "id": "packs.selected",
            "kind": "multi-choice",
            "batch": "simple",
            "prompt": "Which optional packs would you like to enable for this workspace?",
            "required": False,
            "options": optional_packs,
            "recommended": [],
            "default": [],
            "requiredFor": ["packs"],
        })

    if "mcp-config" in policy.get("canonicalSurfaces", []):
        questions.append(mcp_question())

    # ── advanced ─────────────────────────────────────────────────────────────
    for surface in ("agents", "skills"):
        if surface not in ownership_defaults:
            continue
        surface_singular = {"agents": "agent", "skills": "skill"}.get(surface, surface)
        questions.append({
            "id": f"ownership.{surface}",
            "kind": "choice",
            "batch": "advanced",
            "prompt": f"How should {surface_singular} files be managed in this workspace?",
            "required": True,
            "options": [
                {
                    "id": "local",
                    "label": "Local",
                    "description": "Managed by xanadAssistant — files are installed to .github/ and tracked in the lockfile.",
                },
                {
                    "id": "plugin-backed-copilot-format",
                    "label": "Extension-backed",
                    "description": "Managed by the Copilot extension — files use extension format and are registered as Copilot-provided.",
                },
            ],
            "recommended": ownership_defaults[surface],
            "default": ownership_defaults[surface],
            "requiredFor": [surface],
        })

    questions.extend(personalisation_questions())
    questions.extend(settings_questions())

    # ── full ─────────────────────────────────────────────────────────────────
    if "mcp-config" in policy.get("canonicalSurfaces", []):
        questions.append(mcp_servers_question())

    return questions


def expand_interview_questions(
    policy: dict,
    metadata: dict,
    manifest: dict | None,
    mode: str,
    seeded_answers: dict | None = None,
    lockfile_state: dict | None = None,
) -> list[dict]:
    questions = build_interview_questions(policy, metadata, mode)
    if manifest is None:
        return questions

    resolved_answers, _, _ = resolve_question_answers(questions, seeded_answers or {})
    resolved_answers = normalize_plan_answers(policy, resolved_answers)
    pack_questions = build_pack_customization_questions(
        metadata.get("packRegistry") or {},
        resolved_answers,
    )
    return questions + pack_questions + build_agent_customization_questions(
        policy,
        metadata,
        manifest,
        lockfile_state or {},
        resolved_answers,
    )


def _seed_answers(
    mode: str,
    questions: list[dict],
    profile_registry: dict,
    lockfile_state: dict,
    raw: dict,
) -> dict:
    """Seed answers from install state then profile registry for *questions*."""
    ids = {q["id"] for q in questions}
    answers = seed_answers_from_install_state(mode, questions, lockfile_state, raw)
    return seed_answers_from_profile(profile_registry, answers, ids)


def prepare_questions(
    policy: dict,
    metadata: dict,
    manifest: dict | None,
    mode: str,
    lockfile_state: dict,
    raw_answers: dict | None = None,
    *,
    seed_mode: str | None = None,
) -> tuple[list[dict], dict, list[str], list[str]]:
    """Build questions, double-seed answers, expand, and resolve.

    *mode* is used for ``build_interview_questions`` and
    ``expand_interview_questions``.  *seed_mode* is passed to
    ``seed_answers_from_install_state``; when omitted it defaults to *mode*.

    Returns ``(questions, resolved_answers, unresolved_ids, unknown_ids)``.
    """
    actual_seed_mode = seed_mode if seed_mode is not None else mode
    raw = raw_answers or {}
    profile_reg = metadata.get("profileRegistry") or {}
    base_questions = build_interview_questions(policy, metadata, mode)
    answers = _seed_answers(actual_seed_mode, base_questions, profile_reg, lockfile_state, raw)
    questions = expand_interview_questions(policy, metadata, manifest, mode, answers, lockfile_state)
    answers = _seed_answers(actual_seed_mode, questions, profile_reg, lockfile_state, raw)
    resolved, unresolved, unknown = resolve_question_answers(questions, answers)
    return questions, resolved, unresolved, unknown


def _annotate_questions_with_current_values(
    questions: list[dict],
    lockfile_state: dict,
) -> list[dict]:
    """Add currentValue to questions that have an installed answer in the lockfile.

    Only applied for update-mode interviews.  The original default and recommended
    values are preserved so callers can distinguish the package guidance from the
    user's currently-installed choice.
    """
    installed_answers = lockfile_state.get("setupAnswers") or {}
    if not installed_answers:
        return questions
    annotated = []
    for q in questions:
        q_id = q.get("id")
        if q_id and q_id in installed_answers:
            q = {**q, "currentValue": installed_answers[q_id]}
        annotated.append(q)
    return annotated


def build_interview_result(workspace: Path, package_root: Path, mode: str) -> dict:
    context = collect_context(workspace, package_root)
    profile_reg = context["metadata"].get("profileRegistry") or {}
    base_questions = build_interview_questions(context["policy"], context["metadata"], mode)
    seeded_answers = _seed_answers(mode, base_questions, profile_reg, context["lockfileState"], {})
    questions = expand_interview_questions(
        context["policy"], context["metadata"], context["manifest"],
        mode, seeded_answers, context["lockfileState"],
    )

    if mode == "update":
        questions = _annotate_questions_with_current_values(questions, context["lockfileState"])

    if mode == "setup":
        existing_files = scan_existing_copilot_files(workspace, context["manifest"])
    elif mode == "update":
        existing_files = scan_consumer_kept_updates(
            workspace, context["manifest"], context["lockfileState"]
        )
    else:
        existing_files = []

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
            "existingFiles": existing_files,
            "existingFileCount": len(existing_files),
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
    raw_options = question.get("options", [])
    # options may be plain strings or {id, label, description} dicts
    valid_ids = {opt["id"] if isinstance(opt, dict) else opt for opt in raw_options}

    if kind == "choice":
        if not isinstance(value, str) or value not in valid_ids:
            raise LifecycleCommandError(
                "contract_input_failure",
                f"Invalid answer for {question['id']}.",
                4,
                {"questionId": question["id"], "expected": sorted(valid_ids), "received": value},
            )
        return

    if kind == "multi-choice":
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise LifecycleCommandError(
                "contract_input_failure",
                f"Invalid answer for {question['id']}.",
                4,
                {"questionId": question["id"], "expected": sorted(valid_ids), "received": value},
            )
        if any(item not in valid_ids for item in value):
            raise LifecycleCommandError(
                "contract_input_failure",
                f"Invalid answer for {question['id']}.",
                4,
                {"questionId": question["id"], "expected": sorted(valid_ids), "received": value},
            )
        max_sel = question.get("maxSelections")
        if max_sel is not None and len(value) > max_sel:
            raise LifecycleCommandError(
                "contract_input_failure",
                f"Too many selections for {question['id']}: at most {max_sel} allowed.",
                4,
                {"questionId": question["id"], "maxSelections": max_sel, "received": value},
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
