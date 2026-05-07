from __future__ import annotations

from pathlib import Path


DEFAULT_POLICY_PATH = Path("template/setup/install-policy.json")
DEFAULT_POLICY_SCHEMA_PATH = Path("template/setup/install-policy.schema.json")
DEFAULT_MANIFEST_SCHEMA_PATH = Path("template/setup/install-manifest.schema.json")
DEFAULT_LOCK_SCHEMA_PATH = Path("template/setup/xanad-assistant-lock.schema.json")
DEFAULT_PACK_REGISTRY_PATH = Path("template/setup/pack-registry.json")
DEFAULT_PROFILE_REGISTRY_PATH = Path("template/setup/profile-registry.json")
DEFAULT_CATALOG_PATH = Path("template/setup/catalog.json")
DEFAULT_CACHE_ROOT = Path.home() / ".xanad-assistant" / "pkg-cache"


class _State:
    """Mutable module-level session state, shared across all submodules."""
    session_source_info: "dict | None" = None
    log_file = None  # Opened file handle when --log-file is provided.


class LifecycleCommandError(Exception):
    def __init__(self, code: str, message: str, exit_code: int, details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code
        self.details = details or {}
