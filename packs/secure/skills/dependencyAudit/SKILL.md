---
name: dependencyAudit
description: "Dependency vulnerability audit — OSV.dev queries for lockfile packages and CVE triage."
---

# Dependency Audit

Use this skill in workspaces with the secure pack selected.

Query known CVEs for project dependencies using the `secureOsv` hook, which wraps the OSV.dev API (public, no auth required).

## When to audit

- Before releasing or deploying
- When adding or updating a dependency
- When a security advisory is mentioned for a package you use
- As part of a periodic security review

## Using the secureOsv hook

The hook exposes two tools:

**`query_package_vulnerabilities(ecosystem, name, version)`**
- `ecosystem`: `PyPI`, `npm`, `crates.io`, `Go`, `Maven`, `Hex`, `NuGet`, `RubyGems`
- `name`: exact package name as it appears in the lockfile
- `version`: exact installed version string
- Returns: list of OSV IDs, severity (CVSS score and label), fixed-in versions

**`batch_query_lockfile(lockfile_path)`**
- Accepts: `requirements.txt`, `package.json` (dependencies/devDependencies), `Cargo.toml`
- Parses all pinned dependencies and bulk-queries OSV.dev
- Returns: structured list of (package, version, vulnerabilities)

For Go dependencies, use `query_package_vulnerabilities` per package/version; the bulk lockfile parser does not currently support `go.mod`.

## Interpreting results

| CVSS score | Severity | Action |
|---|---|---|
| 9.0–10.0 | Critical | Block release — must fix before shipping |
| 7.0–8.9 | High | Fix before release unless no viable upgrade path |
| 4.0–6.9 | Medium | Fix in next planned dependency update cycle |
| 0.1–3.9 | Low | Track; fix opportunistically |

## Recommended fix path

1. Check the `fixed-in` field from the OSV result — upgrade to that version or later
2. If no fixed version exists, look for an alternative package
3. If neither is available, document the risk and apply mitigations (isolation, input validation, rate limiting) appropriate to the vulnerability type
4. Verify the upgrade does not introduce a breaking API change before committing

## No-hit result

If `batch_query_lockfile` returns zero vulnerabilities, report: "No known vulnerabilities found in `<lockfile>` as of `<query date>`." Do not treat a clean result as a permanent guarantee.
