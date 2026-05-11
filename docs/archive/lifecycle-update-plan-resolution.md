
## Bootstrap And Package Resolution

The bootstrap path should be small, auditable, and standard-library only.

Responsibilities:

- Resolve package source from GitHub release, branch, commit, or local path.
- Download the lifecycle package or locate it on disk.
- Verify manifest presence and, when release metadata exists, expected hashes.
- Refuse unsafe or ambiguous sources unless explicitly requested.
- Cache downloaded package content in a predictable temporary or user-cache location.
- Hand off to the lifecycle engine.

Default source policy:

- normal users: GitHub release, `--version latest`
- development: explicit `--ref main` or local `--package-root`
- reproducible repair: lockfile-pinned version or commit when available

## Engine Layers

The script should be internally split into modules even if the first implementation ships as one file.

### Bootstrap Layer

Handles source resolution, download, cache location, and handoff.

### Package Loader

Loads policy, generated manifest, schemas, release metadata, and package files.

### Workspace Inspector

Detects repository state:

- Git repository presence and dirty working tree
- existing `.github/copilot-instructions.md`
- existing `.github/instructions/`, `.github/prompts/`, `.github/agents/`, `.github/skills/`
- existing hooks and MCP config
- VS Code settings and extension recommendations
- prior lockfile or legacy version file
- installed ownership modes
- local custom files not managed by the package
- language/framework hints useful for setup questions

### Interview Schema

Defines required questions as data, not prose embedded only in an agent.

The script should emit question objects such as:

```json
{
  "id": "mcp.fetch.enabled",
  "kind": "confirm",
  "prompt": "Enable the fetch MCP server for this workspace?",
  "default": true,
  "recommended": true,
  "reason": "The package can install the required local hook script atomically.",
  "requiredFor": ["mcp.fetch"]
}
```

Copilot can present those questions conversationally and return `answers.json`.

Default MCP enablement should be treated as lifecycle policy, not as a proxy for whether a server might make outbound requests at runtime. Runtime network capabilities belong in per-server documentation, approval flows, or sandbox policy.

### Planner

Builds a complete no-write plan.

The plan must include:

- files to add
- files to replace
- files to merge
- files to preserve
- files to skip by policy
- retired files to report or archive
- hook and MCP atomicity actions
- chmod actions
- token substitutions
- backup paths
- lockfile writes
- validation steps
- risk level and approval summary

### Applier

Executes an approved plan.

Rules:

- Create a timestamped backup before the first write.
- Write to temporary files where practical, then replace atomically.
- Apply all selected actions as one transaction as far as the filesystem allows.
- Stop on validation failure and report partial state clearly.
- Never modify files not present in the approved plan.

### Reporter

Produces:

- JSON report for Copilot and tests
- concise terminal receipt for the human
- detailed log file for debugging
- optional Markdown summary for `.github/copilot-version.md`

### Lockfile Manager

Owns `.github/xanadAssistant-lock.json` and repairs legacy state.

## Manifest And Policy Model

Do not hand-maintain an exhaustive manifest. Use a smaller human-authored policy file plus a generator.

### Human-Authored Policy

`template/setup/install-policy.json` should define:

- canonical surfaces
- source roots
- target path rules
- ownership defaults
- strategy defaults
- required conditions
- token rules
- chmod rules
- retired-file policy
- package-format delivery rules

### Generated Manifest

`template/setup/install-manifest.json` should include full file entries with computed hashes.

Example entry:

```json
{
  "id": "hooks.scripts.mcp-fetch-server",
  "surface": "hooks",
  "source": "hooks/scripts/mcp-fetch-server.py",
  "target": ".github/hooks/scripts/mcp-fetch-server.py",
  "ownership": ["local", "plugin-backed-copilot-format"],
  "strategy": "replace-verbatim",
  "requiredWhen": ["mcp.fetch.enabled", "mcp.fetch.available"],
  "tokens": [],
  "chmod": "executable-if-shell",
  "hash": "sha256:<full digest>",
  "introducedIn": "0.10.0"
}
```

Required surfaces:

- core instructions from `template/copilot-instructions.md`
- path instructions from `template/instructions/`
- prompts from `template/prompts/`
- agents from `agents/` when local ownership applies
- skills from `skills/` when local ownership applies
- hook config from `template/hooks/copilot-hooks.json`
- hook scripts from `hooks/scripts/`
- MCP config from `template/vscode/mcp.json` or `template/vscode/mcp-unsandboxed.json`
- VS Code settings and extension recommendations
- workspace files from `template/workspace/`
- starter kits from `starter-kits/`
- Claude compatibility files and workflow files
The manifest should also declare retired managed files so the updater can report, archive, or remove them according to policy.

