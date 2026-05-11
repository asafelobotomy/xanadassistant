from __future__ import annotations

from scripts.lifecycle._xanad._state import CURRENT_PACKAGE_NAME, get_lockfile_package_name

def seed_answers_from_install_state(mode: str, questions: list[dict], lockfile_state: dict, answers: dict) -> dict:
    if mode not in {"update", "repair", "factory-restore"}:
        return dict(answers)

    seeded_answers = dict(answers)
    question_map = {question["id"]: question for question in questions}

    profile_question = question_map.get("profile.selected")
    installed_profile = lockfile_state.get("profile")
    if profile_question and "profile.selected" not in seeded_answers and installed_profile in profile_question.get("options", []):
        seeded_answers["profile.selected"] = installed_profile

    packs_question = question_map.get("packs.selected")
    installed_packs = lockfile_state.get("selectedPacks", [])
    if packs_question and "packs.selected" not in seeded_answers and isinstance(installed_packs, list):
        valid_packs = [pack_id for pack_id in installed_packs if pack_id in packs_question.get("options", [])]
        seeded_answers["packs.selected"] = valid_packs

    # Re-seed all personalisation answers that were recorded at apply time.
    # This ensures check/update/repair re-derives the same token values as the
    # original apply, preventing false-stale reports after non-default answers.
    installed_setup_answers = lockfile_state.get("setupAnswers", {})
    if isinstance(installed_setup_answers, dict):
        for answer_id, value in installed_setup_answers.items():
            if answer_id not in seeded_answers and answer_id in question_map:
                seeded_answers[answer_id] = value

    # Re-seed mcp.enabled from lockfile installMetadata so that hook/mcp entries
    # that were skipped at apply time are not re-classified as missing by check.
    mcp_enabled = lockfile_state.get("mcpEnabled")
    if mcp_enabled is not None and "mcp.enabled" not in seeded_answers:
        seeded_answers["mcp.enabled"] = mcp_enabled

    return seeded_answers


def seed_answers_from_profile(profile_registry: dict, answers: dict, question_ids: set[str] | None = None) -> dict:
    """Apply a selected profile's defaultPacks and setupAnswerDefaults into answers for any key not already set."""
    selected_profile = answers.get("profile.selected")
    if not selected_profile:
        return answers

    profiles = {profile["id"]: profile for profile in profile_registry.get("profiles", [])}
    profile = profiles.get(selected_profile)
    if profile is None:
        return answers

    seeded = dict(answers)

    for key, value in profile.get("setupAnswerDefaults", {}).items():
        if question_ids is not None and key not in question_ids:
            continue
        if key not in seeded:
            seeded[key] = value

    default_packs = profile.get("defaultPacks", [])
    if default_packs and "packs.selected" not in seeded:
        seeded["packs.selected"] = list(default_packs)

    return seeded


def determine_repair_reasons(context: dict) -> list[str]:
    reasons: list[str] = []
    if context["installState"] == "legacy-version-only":
        reasons.append("legacy-version-only")
    if context["legacyVersionState"]["malformed"]:
        reasons.append("malformed-legacy-version")
    if context["lockfileState"]["malformed"]:
        reasons.append("malformed-lockfile")
    if context["lockfileState"].get("needsMigration"):
        reasons.append("schema-migration-required")
    installed_package_name = context["lockfileState"].get("originalPackageName") or get_lockfile_package_name(context["lockfileState"])
    if installed_package_name is not None and installed_package_name != CURRENT_PACKAGE_NAME:
        reasons.append("package-identity-migration-required")
    if context.get("successorMigrationTargets"):
        reasons.append("successor-cleanup-required")
    if context["installState"] == "installed" and not context["lockfileState"].get("malformed"):
        manifest_with_status = context.get("manifestWithStatus")
        if manifest_with_status is not None:
            for entry in manifest_with_status.get("managedFiles", []):
                if entry.get("status") == "missing" and "skipReason" not in entry:
                    reasons.append("incomplete-install")
                    break
    return reasons
