"""Static section additions for add_skill_sections.py (group B)."""

from __future__ import annotations


ADDITIONS = {
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