from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))  # pragma: no cover

# Re-export all public symbols so that existing imports and mock patches keep working.
from scripts.lifecycle._xanad._errors import (  # noqa: E402
    LifecycleCommandError, _State,
    DEFAULT_POLICY_PATH, DEFAULT_POLICY_SCHEMA_PATH, DEFAULT_MANIFEST_SCHEMA_PATH,
    DEFAULT_LOCK_SCHEMA_PATH, DEFAULT_PACK_REGISTRY_PATH, DEFAULT_PROFILE_REGISTRY_PATH,
    DEFAULT_CATALOG_PATH, DEFAULT_CACHE_ROOT,
)
from scripts.lifecycle._xanad._cli import add_common_arguments, build_parser
from scripts.lifecycle._xanad._source import (
    resolve_workspace, resolve_package_root, get_cache_root,
    parse_github_source, resolve_github_release, resolve_github_ref,
    resolve_effective_package_root, build_source_summary,
)
from scripts.lifecycle._xanad._loader import (
    load_optional_json, load_contract_artifacts, load_discovery_metadata, load_manifest,
)
from scripts.lifecycle.generate_manifest import load_json, sha256_file  # noqa: F401
from scripts.lifecycle._xanad._state import (
    detect_git_state, determine_install_state, parse_legacy_version_file,
    _lockfile_needs_migration, migrate_lockfile_shape, parse_lockfile_state,
    read_lockfile_status, count_files, detect_existing_surfaces, summarize_manifest_targets,
)
from scripts.lifecycle._xanad._conditions import (
    parse_condition_literal, condition_matches, entry_required_for_plan,
    normalize_plan_answers, resolve_token_values, render_tokenized_text,
)
from scripts.lifecycle._xanad._merge import (
    sha256_bytes, sha256_json, merge_json_objects, serialize_json_object,
    extract_markdown_heading_block, extract_marked_markdown_blocks,
    merge_markdown_with_preserved_blocks,
)
from scripts.lifecycle._xanad._plan_utils import (
    expected_entry_bytes, expected_entry_hash, build_token_plan_summary, build_backup_plan,
)
from scripts.lifecycle._xanad._inspect import (
    collect_context, build_inspect_result, annotate_manifest_entries,
    classify_manifest_entries, collect_unmanaged_files,
)
from scripts.lifecycle._xanad._check import build_check_result
from scripts.lifecycle._xanad._interview import (
    build_interview_questions, build_interview_result, build_error_payload,
    load_answers, validate_answer_value, resolve_question_answers,
)
from scripts.lifecycle._xanad._defaults import derive_effective_plan_defaults
from scripts.lifecycle._xanad._plan_a import (
    resolve_ownership_by_surface, build_setup_plan_actions,
    classify_plan_conflicts, build_conflict_summary,
    write_plan_output,
    verify_manifest_integrity,
)
from scripts.lifecycle._xanad._plan_c import (
    seed_answers_from_install_state, seed_answers_from_profile,
    determine_repair_reasons,
)
from scripts.lifecycle._xanad._plan_b import (
    _build_lockfile_package_info, build_planned_lockfile,
    build_plan_result,
)
from scripts.lifecycle._xanad._apply import (
    generate_apply_timestamps, materialize_apply_timestamp, render_entry_bytes,
    merge_json_object_file, merge_markdown_file, build_copilot_version_summary,
    apply_chmod_rule,
)
from scripts.lifecycle._xanad._execute_apply import (
    execute_apply_plan, build_execution_result, build_apply_result,
)
from scripts.lifecycle._xanad._emit import emit_json, emit_json_lines
from scripts.lifecycle._xanad._progress import (
    emit_agent_progress, emit_payload, build_not_implemented_payload,
)
from scripts.lifecycle._xanad._main import main

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
