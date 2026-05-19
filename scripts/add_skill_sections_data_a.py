"""Static section additions for add_skill_sections.py (group A)."""

from __future__ import annotations


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
}