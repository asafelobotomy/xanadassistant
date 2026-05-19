"""One-off script: add ## When to use, ## When NOT to use, ## Verify to pack SKILL.md files."""

import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Per-file additions: (when_to_use_bullets, when_not_to_use_bullets, verify_bullets)
ADDITIONS = {
    "packs/devops/skills/devopsCiCd/SKILL.md": (
        [
            "Designing, reviewing, or debugging CI/CD pipeline definitions",
            "Setting up new pipeline stages, environment gates, or artifact workflows",
        ],
        [
            "When reviewing Dockerfiles or container images specifically — prefer `devopsContainers`",
            "When reviewing IaC definitions — prefer `devopsInfraAsCode`",
            "When performing a full deployment-risk review — prefer `devopsReview`",
        ],
        [
            "Applied the pipeline stage model (Validate → Test → Build → Security → Deploy)",
            "Job naming and runner version follow conventions",
            "No mutable branch references or echoed secrets in the pipeline YAML",
        ],
    ),
    "packs/devops/skills/devopsContainers/SKILL.md": (
        [
            "Writing or reviewing Dockerfiles, container compose files, or image-build pipelines",
            "Auditing a container image for security posture, layer hygiene, or build reproducibility",
        ],
        [
            "When reviewing IaC or pipeline YAML that does not touch image builds — prefer `devopsInfraAsCode` or `devopsCiCd`",
            "When reviewing a full infrastructure PR for deployment risk — prefer `devopsReview`",
        ],
        [
            "Multi-stage build used where applicable; runtime image is minimal",
            "No root-user execution without explicit justification",
            "Base image pinned to a minor version or digest — not `:latest`",
            "`.dockerignore` excludes `.git`, `*.env`, and dev artifacts",
        ],
    ),
    "packs/devops/skills/devopsInfraAsCode/SKILL.md": (
        [
            "Writing or reviewing Terraform, Pulumi, or similar IaC definitions",
            "Auditing IaC for state management, naming, modularity, or drift-detection discipline",
        ],
        [
            "When reviewing container images or Dockerfiles — prefer `devopsContainers`",
            "When reviewing CI/CD pipeline YAML only — prefer `devopsCiCd`",
        ],
        [
            "Applied core IaC principles (state locked, plan before apply, least privilege)",
            "Naming conventions and file organisation follow the prescribed conventions",
            "No console-click changes implied; mutable or unlocked state flagged",
        ],
    ),
    "packs/devops/skills/devopsReview/SKILL.md": (
        [
            "Reviewing CI/CD pipelines, Dockerfiles, IaC definitions, deployment scripts, or infrastructure PRs",
        ],
        [
            "When reviewing source code for logic or application-layer security — prefer `secureReview`",
            "When reviewing documentation only — prefer `docsReview`",
        ],
        [
            "All applicable tiers run; findings reported with `secret:`, `privilege:`, `rollback:`, `risk:`, `hygiene:`, or `nit:` prefix",
            "Tier 1 blockers identified and acknowledged before proceeding to Tier 2",
            "Rollback checklist applied for any production-facing change",
        ],
    ),
    "packs/docs/skills/docsApi/SKILL.md": (
        [
            "Documenting code: functions, classes, REST endpoints, CLI commands, or configuration schemas",
        ],
        [
            "When writing user-facing guides or tutorials — prefer `docsStructure`",
            "When reviewing existing documentation for accuracy — prefer `docsReview`",
        ],
        [
            "Correct docstring format used for the target language",
            "All required fields present (args, returns, raises, or equivalent)",
            "Parameter names, types, and defaults match the current implementation",
        ],
    ),
    "packs/docs/skills/docsReview/SKILL.md": (
        [
            "Reviewing documentation before it is merged or published",
        ],
        [
            "When the PR contains no documentation changes",
            "When reviewing code logic rather than documentation — prefer `secureReview` or `devopsReview`",
        ],
        [
            "All four tiers run; findings reported with `accuracy:`, `missing:`, `clarity:`, `link:`, or `nit:` prefix",
            "All Tier 1 `accuracy:` and Tier 2 `missing:` findings identified before suggesting approve",
        ],
    ),
    "packs/docs/skills/docsStructure/SKILL.md": (
        [
            "Planning, scaffolding, or reorganising documentation",
            "Choosing the correct Diátaxis document type and section order before drafting",
        ],
        [
            "When reviewing finished documentation for accuracy — prefer `docsReview`",
            "When editing prose style and register — prefer `docsStyle`",
        ],
        [
            "Correct Diátaxis type identified for the document (Tutorial / How-to / Reference / Explanation)",
            "Appropriate section template applied; document types are not mixed in a single file",
        ],
    ),
    "packs/docs/skills/docsStyle/SKILL.md": (
        [
            "Drafting or reviewing any user-facing documentation: READMEs, guides, API references, changelogs, or inline code comments",
        ],
        [
            "When reviewing for technical accuracy — prefer `docsReview`",
            "When writing code docstrings in a language with dedicated conventions — prefer `docsApi`",
        ],
        [
            "Active voice, imperative mood, and short-sentence rules applied",
            "Prescribed term list used; no synonym drift",
            "No passive constructions, filler phrases, or second-person avoidance",
        ],
    ),
    "packs/lean/skills/leanAndon/SKILL.md": (
        [
            "Workspaces with the lean pack selected, when deciding whether to stop and ask or proceed autonomously",
        ],
        [
            "Outside workspaces with the lean pack selected",
            "When the user has already explicitly confirmed the action in the current turn",
        ],
        [
            "Applied the three cord-pull conditions strictly (irreversible + unconfirmed, critical absent info, two materially different interpretations)",
            "Did not pull the cord for general caution alone",
            "Cord decision documented if pulled",
        ],
    ),
    "packs/lean/skills/leanContext/SKILL.md": (
        [
            "Workspaces with the lean pack selected, when managing context window hygiene across turns",
        ],
        [
            "Outside workspaces with the lean pack selected",
            "When the context is genuinely needed to continue — defer rather than prune",
        ],
        [
            "Raw tool results pruned after answers derived; conclusions retained",
            "Completed intermediate steps not re-read or re-run this session",
            "Unchanged-state confirmations omitted unless ambiguity requires them",
        ],
    ),
    "packs/lean/skills/leanOutput/SKILL.md": (
        [
            "Workspaces with the lean pack selected, when generating responses, summaries, receipts, or reports",
        ],
        [
            "Outside workspaces with the lean pack selected",
            "When the user explicitly requests expanded or detailed output",
        ],
        [
            "One-line descriptions used; plan writes summarised as counts only (added: N, replaced: N)",
            "No filler phrases (`I will now`, `Here is`, `As requested`)",
            "No unchanged-state commentary where state is obvious",
        ],
    ),
    "packs/lean/skills/leanVerification/SKILL.md": (
        [
            "Workspaces with the lean pack selected, when running or reporting on tests, linters, type checkers, or validation steps",
        ],
        [
            "Outside workspaces with the lean pack selected",
            "When the user explicitly requests verbose test output or a full run transcript",
        ],
        [
            "Passing runs reported as a single summary line only",
            "Failing runs include file, line, and message only — no stack-trace prose",
            "No per-test narration for passing tests",
        ],
    ),
    "packs/mlops/skills/mlopsDataPipelines/SKILL.md": (
        [
            "Designing, reviewing, or debugging ML data pipelines",
        ],
        [
            "When reviewing model serving infrastructure — prefer `mlopsModelServing`",
            "When reviewing experiment tracking only — prefer `mlopsExperiments`",
        ],
        [
            "Core data pipeline principles applied; no leakage across train/val/test splits",
            "Dataset version pinned (DVC, S3 URI with hash, or registry entry)",
            "Schema validation present at pipeline entry",
        ],
    ),
    "packs/mlops/skills/mlopsExperiments/SKILL.md": (
        [
            "Designing, running, or reviewing machine learning experiments",
        ],
        [
            "When deploying models to production — prefer `mlopsModelServing`",
            "When reviewing data pipeline code — prefer `mlopsDataPipelines`",
        ],
        [
            "Reproducibility confirmed: seeds, dataset versions, and hyperparameters logged at run start",
            "Single north-star metric defined before the experiment",
            "Baseline run documented; no cherry-picking metrics after the run",
        ],
    ),
    "packs/mlops/skills/mlopsModelServing/SKILL.md": (
        [
            "Deploying, versioning, or monitoring ML models in production",
        ],
        [
            "When setting up experiment tracking — prefer `mlopsExperiments`",
            "When reviewing data pipeline code — prefer `mlopsDataPipelines`",
        ],
        [
            "Model registered in registry with version tag before any production deploy",
            "Stage gate followed (Staging → Production, not direct to Production)",
            "Canary or A/B rollout plan present; rollback documented and previous version retained",
        ],
    ),
    "packs/mlops/skills/mlopsReview/SKILL.md": (
        [
            "Reviewing ML code, notebooks, pipeline definitions, or model deployment PRs",
        ],
        [
            "When reviewing non-ML source code — prefer `devopsReview` or `secureReview`",
            "When reviewing documentation — prefer `docsReview`",
        ],
        [
            "All applicable tiers run; findings reported with `leakage:`, `reproducibility:`, `bias:`, `data:`, `hygiene:`, or `nit:` prefix",
            "Tier 1 safety blockers identified before proceeding to Tier 2",
            "Bias and fairness flags applied when the model affects people",
        ],
    ),
    "packs/oss/skills/ossChangelog/SKILL.md": (
        [
            "Maintaining a CHANGELOG, generating release notes, or formatting version entries",
        ],
        [
            "When writing code documentation — prefer `docsApi`",
            "When drafting contribution guidelines — prefer `ossContributing`",
        ],
        [
            "Keep a Changelog format used; `[Unreleased]` section present",
            "Version entries include all applicable categories (Added, Changed, Deprecated, Removed, Fixed, Security)",
            "Semantic versioning rules applied to the version bump",
        ],
    ),
    "packs/oss/skills/ossCodeReview/SKILL.md": (
        [
            "Reviewing OSS pull requests",
            "When a maintainer needs structured guidance on what to check before merging",
        ],
        [
            "When reviewing internal private code for security — prefer `secureReview`",
            "When reviewing documentation only — prefer `docsReview`",
        ],
        [
            "All five tiers run (Correctness, Tests, API compatibility, Documentation, License & DCO)",
            "Verdict given as Approve, Request Changes, or Comment with tier-level justification",
        ],
    ),
    "packs/oss/skills/ossContributing/SKILL.md": (
        [
            "Answering questions about contribution workflows, CONTRIBUTING.md structure, or preparing a first contribution to an open-source project",
        ],
        [
            "When reviewing a specific open PR — prefer `ossCodeReview`",
            "When handling licensing questions — prefer `ossLicensing`",
        ],
        [
            "CONTRIBUTING.md covers all required sections (Code of Conduct, Getting started, Workflow, Commit format, PR checklist)",
            "DCO or CLA requirements stated; contributor onboarding checklist present",
        ],
    ),
    "packs/oss/skills/ossLicensing/SKILL.md": (
        [
            "Choosing a license, adding a LICENSE file, checking license compatibility, or using SPDX identifiers correctly",
        ],
        [
            "When reviewing the contribution process — prefer `ossContributing`",
            "When reviewing code for security issues — prefer `secureReview`",
        ],
        [
            "LICENSE file present and correctly formatted for the chosen license",
            "SPDX identifier used in file headers where required",
            "License compatibility checked when mixing dependencies with different licenses",
        ],
    ),
    "packs/secure/skills/dependencyAudit/SKILL.md": (
        [
            "Before releasing or deploying",
            "When adding or updating a dependency",
            "When a security advisory is mentioned for a package in use",
            "As part of a periodic security review",
        ],
        [
            "When reviewing source code for logic bugs — prefer `secureReview`",
            "When the workspace has no package lockfile to audit",
        ],
        [
            "Queried OSV.dev (or equivalent) for all direct dependencies",
            "Each CVE triaged with severity, affected version range, and patch status",
            "Findings reported with ecosystem, package, version, and CVE ID",
        ],
    ),
    "packs/secure/skills/secretScanning/SKILL.md": (
        [
            "Before staging or committing files that may contain credentials, tokens, or connection strings",
        ],
        [
            "When the file has already been committed and the secret revoked — use `git-filter-repo` instead",
            "When scanning for code logic issues — prefer `secureReview`",
        ],
        [
            "Applied both high-confidence and medium-confidence secret patterns",
            "Probable secrets surfaced for user confirmation before staging",
            "No known-pattern false negatives (AWS keys, GitHub tokens, private key headers, connection strings)",
        ],
    ),
    "packs/secure/skills/secureReview/SKILL.md": (
        [
            "Performing security-focused code review in workspaces with the secure pack selected",
        ],
        [
            "When reviewing infrastructure or deployment code — prefer `devopsReview`",
            "When dependency scanning is the primary goal — prefer `dependencyAudit`",
        ],
        [
            "Each finding mapped to an OWASP Top 10:2025 category",
            "Prescribed severity levels used (Critical, High, Medium, Low)",
            "Purely stylistic findings not reported",
        ],
    ),
    "packs/secure/skills/threatModel/SKILL.md": (
        [
            "Modeling a new user-facing feature, API endpoint, authentication flow, or integration with external services",
            "Any feature handling sensitive data, authentication, authorization, or with financial or compliance implications",
        ],
        [
            "When reviewing already-deployed, stable, unchanged infrastructure",
            "When reviewing code style or documentation only",
        ],
        [
            "Trust boundaries and assets identified",
            "All six STRIDE categories applied (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege)",
            "Each threat documented with ID, category, description, and suggested mitigation",
        ],
    ),
    "packs/shapeup/skills/shapeupBetting/SKILL.md": (
        [
            "Running or participating in a Shape Up betting table",
            "Evaluating pitches for the next cycle, setting appetite, or deciding which pitches to bet on",
        ],
        [
            "When writing a new pitch — prefer `shapeupPitching`",
            "When managing in-cycle work — prefer `shapeupCycleWork`",
        ],
        [
            "Only pitches with all five elements at the table",
            "Bets recorded with team size and cycle time; unbet pitches explicitly declined rather than deferred",
        ],
    ),
    "packs/shapeup/skills/shapeupCycleWork/SKILL.md": (
        [
            "Managing in-cycle scope during a Shape Up cycle",
            "Using hill charts, applying scope hammering, or deciding whether to invoke the circuit breaker",
        ],
        [
            "When writing a pitch — prefer `shapeupPitching`",
            "When running the betting table — prefer `shapeupBetting`",
        ],
        [
            "Hill chart updated; each task placed correctly (uphill = unknowns remain, downhill = approach settled)",
            "Scope hammering applied when timeline is at risk; no scope creep",
            "Circuit breaker invoked only if work cannot ship within the fixed time box",
        ],
    ),
    "packs/shapeup/skills/shapeupPitching/SKILL.md": (
        [
            "Drafting, reviewing, or refining a Shape Up pitch",
            "Preparing a pitch for the betting table",
        ],
        [
            "When the betting table is already in progress — prefer `shapeupBetting`",
            "When managing active in-cycle work — prefer `shapeupCycleWork`",
        ],
        [
            "All five elements present: Problem, Appetite, Solution, Rabbit holes, No-gos",
            "No solution disguised as a problem statement",
            "Appetite stated as S (1–2 weeks), M (4 weeks), or L (6 weeks)",
        ],
    ),
    "packs/shapeup/skills/shapeupReview/SKILL.md": (
        [
            "Auditing a pitch for completeness",
            "Reviewing in-cycle scope discipline or validating that a betting table decision meets Shape Up principles",
        ],
        [
            "When writing a new pitch from scratch — prefer `shapeupPitching`",
            "When actively running a betting table — prefer `shapeupBetting`",
        ],
        [
            "All review tiers run; blocking issues reported before non-blocking",
            "Output uses prescribed verdict format",
        ],
    ),
    "packs/tdd/skills/tddCycle/SKILL.md": (
        [
            "Workspaces with the tdd pack selected, when applying Red-Green-Refactor as the fundamental unit of work",
        ],
        [
            "Outside workspaces with the tdd pack selected",
            "When reviewing existing test architecture — prefer `testArchitecture`",
        ],
        [
            "Test written before implementation confirmed (Red phase)",
            "Minimal implementation only — no premature abstraction (Green phase)",
            "Refactor left all tests green; one new behavior per cycle",
        ],
    ),
    "packs/tdd/skills/testArchitecture/SKILL.md": (
        [
            "Structuring a test suite; separating unit from integration tests; deciding what a test should and should not cross as a boundary",
        ],
        [
            "When applying the TDD cycle itself — prefer `tddCycle`",
            "When analyzing coverage gaps in an existing suite — prefer `testCoverage`",
        ],
        [
            "Test pyramid respected (unit > integration > e2e in count and speed)",
            "Each test layer has clear boundary rules; no cross-layer coupling",
        ],
    ),
    "packs/tdd/skills/testCoverage/SKILL.md": (
        [
            "Workspaces with the tdd pack selected, when analyzing coverage gaps, interpreting coverage reports, or deciding on coverage targets",
        ],
        [
            "When writing new tests from scratch — prefer `tddCycle`",
            "When reviewing test architecture decisions — prefer `testArchitecture`",
        ],
        [
            "Branch coverage reported, not only line coverage",
            "Meaningful gaps identified (untested paths, not just low-count lines)",
            "Coverage treated as a diagnostic signal, not as a target metric",
        ],
    ),
    "packs/tdd/skills/testDoubles/SKILL.md": (
        [
            "Workspaces with the tdd pack selected, when choosing the right test double type for isolation or interaction verification",
        ],
        [
            "Outside workspaces with the tdd pack selected",
            "When the component under test has no external dependencies to isolate",
        ],
        [
            "Most minimal double type chosen for the test goal (dummy < stub < fake < spy < mock)",
            "No over-mocking; flagged if more than 3 mocks appear in a single test",
        ],
    ),
}


def format_bullets(bullets: list[str]) -> str:
    return "\n".join(f"- {b}" for b in bullets)


def add_sections(path: str, when_to: list[str], when_not: list[str], verify: list[str]) -> None:
    full_path = os.path.join(REPO, path)
    with open(full_path, encoding="utf-8") as f:
        content = f.read()

    # Skip if already has the required headers
    if "## When to use" in content and "## When NOT to use" in content and "## Verify" in content:
        print(f"SKIP (already complete): {path}")
        return

    # Find the position of the first ## section after the title
    # Insert When to use / When NOT to use before it
    first_section = re.search(r"^## ", content, re.MULTILINE)
    if not first_section:
        print(f"WARNING: no ## section found in {path}")
        return

    insert_pos = first_section.start()

    when_to_block = f"## When to use\n\n{format_bullets(when_to)}\n\n"
    when_not_block = f"## When NOT to use\n\n{format_bullets(when_not)}\n\n"

    # Only add sections that don't exist
    inject = ""
    if "## When to use" not in content:
        inject += when_to_block
    if "## When NOT to use" not in content:
        inject += when_not_block

    if inject:
        content = content[:insert_pos] + inject + content[insert_pos:]

    # Append Verify at end if missing
    if "## Verify" not in content:
        verify_items = "\n".join(f"- [ ] {b}" for b in verify)
        content = content.rstrip() + f"\n\n## Verify\n\n{verify_items}\n"

    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"OK: {path}")


if __name__ == "__main__":
    for rel_path, (wtu, wnu, verify) in ADDITIONS.items():
        add_sections(rel_path, wtu, wnu, verify)
    print("Done.")
