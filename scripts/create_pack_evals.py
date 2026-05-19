"""One-off script: create minimal eval stubs for all pack SKILL.md files."""

import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SKILLS = {
    "devopsCiCd": ("pipeline stage model or CI/CD", "CI/CD pipeline design or review"),
    "devopsContainers": ("Dockerfile or container", "container image or Dockerfile review"),
    "devopsInfraAsCode": ("IaC|Terraform|Pulumi", "infrastructure-as-code review"),
    "devopsReview": ("secret:|rollback:|privilege:", "DevOps PR review with tiered checklist"),
    "docsApi": ("docstring|endpoint|Args|Returns", "API documentation"),
    "docsReview": ("accuracy:|missing:|clarity:", "documentation review with tiered checklist"),
    "docsStructure": ("Tutorial|How-to|Reference|Explanation|Diátaxis", "documentation structure planning"),
    "docsStyle": ("active voice|imperative|present tense", "documentation style review"),
    "leanAndon": ("pull the cord|proceed|irreversible", "Andon cord stop-or-proceed decision"),
    "leanContext": ("prune|defer|context", "context window hygiene"),
    "leanOutput": ("added:|replaced:|pass/fail", "lean output formatting"),
    "leanVerification": ("Ran:|pass|fail", "lean verification reporting"),
    "mlopsDataPipelines": ("DVC|leakage|split|train", "ML data pipeline design or review"),
    "mlopsExperiments": ("reproducib|seed|baseline|metric", "ML experiment design or review"),
    "mlopsModelServing": ("registry|canary|rollback|drift", "ML model serving deployment"),
    "mlopsReview": ("leakage:|reproducibility:|bias:", "ML code review with tiered checklist"),
    "ossChangelog": ("Unreleased|Added|Fixed|Changed", "OSS changelog maintenance"),
    "ossCodeReview": ("Correctness|Tests|API compat", "OSS pull request review"),
    "ossContributing": ("CONTRIBUTING|DCO|CLA|onboarding", "OSS contribution workflow guidance"),
    "ossLicensing": ("LICENSE|SPDX|MIT|Apache|GPL", "OSS license guidance"),
    "dependencyAudit": ("CVE|OSV|severity|ecosystem", "dependency vulnerability audit"),
    "secretScanning": ("secret|token|credential|private key", "secret scanning before commit"),
    "secureReview": ("OWASP|A0[0-9]|Critical|High|Medium", "OWASP-mapped security review"),
    "threatModel": ("STRIDE|trust boundary|mitigation|threat", "STRIDE threat model"),
    "shapeupBetting": ("betting table|appetite|pitch", "Shape Up betting table"),
    "shapeupCycleWork": ("hill chart|scope hammer|circuit breaker", "Shape Up cycle execution"),
    "shapeupPitching": ("Problem|Appetite|Solution|Rabbit holes|No-gos", "Shape Up pitch writing"),
    "shapeupReview": ("Tier 1|blocking|pitch|scope discipline", "Shape Up review"),
    "tddCycle": ("Red|Green|Refactor", "TDD Red-Green-Refactor cycle"),
    "testArchitecture": ("unit|integration|pyramid|boundary", "test suite architecture"),
    "testCoverage": ("branch coverage|mutation|diagnostic", "test coverage analysis"),
    "testDoubles": ("stub|mock|fake|spy|dummy", "test double selection"),
}

PACK_MAP = {
    "devopsCiCd": "devops", "devopsContainers": "devops", "devopsInfraAsCode": "devops", "devopsReview": "devops",
    "docsApi": "docs", "docsReview": "docs", "docsStructure": "docs", "docsStyle": "docs",
    "leanAndon": "lean", "leanContext": "lean", "leanOutput": "lean", "leanVerification": "lean",
    "mlopsDataPipelines": "mlops", "mlopsExperiments": "mlops", "mlopsModelServing": "mlops", "mlopsReview": "mlops",
    "ossChangelog": "oss", "ossCodeReview": "oss", "ossContributing": "oss", "ossLicensing": "oss",
    "dependencyAudit": "secure", "secretScanning": "secure", "secureReview": "secure", "threatModel": "secure",
    "shapeupBetting": "shapeup", "shapeupCycleWork": "shapeup", "shapeupPitching": "shapeup", "shapeupReview": "shapeup",
    "tddCycle": "tdd", "testArchitecture": "tdd", "testCoverage": "tdd", "testDoubles": "tdd",
}

EVAL_YAML = """\
name: "{skill}-eval"
description: "Evaluates {skill} skill behaviour"

graders:
  - type: text
    name: references_skill
    config:
      pattern: "(?i)({pattern})"

tasks:
  - "tasks/*.yaml"
"""

TASK_YAML = """\
id: basic-invocation
description: "Verify skill produces output appropriate for {description}"
prompt: |
  Run the {skill} skill. Apply it to a relevant example and produce the
  expected output, checklist findings, or recommendations as defined by the skill.
expected:
  - "{expected1}"
tags:
  - basic
  - smoke
"""


def create_eval(skill: str, pattern: str, description: str) -> None:
    pack = PACK_MAP[skill]
    # xanadEval resolves eval path as 3 parents up from SKILL.md:
    # packs/<pack>/skills/<skill>/SKILL.md → .parent×3 = packs/<pack>/
    # so evals go at packs/<pack>/evals/<skill>/eval.yaml
    eval_dir = os.path.join(REPO, "packs", pack, "evals", skill)
    tasks_dir = os.path.join(eval_dir, "tasks")

    eval_path = os.path.join(eval_dir, "eval.yaml")
    task_path = os.path.join(tasks_dir, "basic-invocation.yaml")

    if os.path.exists(eval_path):
        print(f"SKIP (exists): packs/{pack}/evals/{skill}/eval.yaml")
        return

    os.makedirs(tasks_dir, exist_ok=True)

    # Pick the first alternative in the pattern as the expected keyword
    expected1 = pattern.split("|")[0].replace("\\", "")

    with open(eval_path, "w", encoding="utf-8") as f:
        f.write(EVAL_YAML.format(skill=skill, pattern=pattern))

    with open(task_path, "w", encoding="utf-8") as f:
        f.write(TASK_YAML.format(skill=skill, description=description, expected1=expected1))

    print(f"OK: packs/{pack}/evals/{skill}/")


if __name__ == "__main__":
    for skill, (pattern, description) in SKILLS.items():
        create_eval(skill, pattern, description)
    print("Done.")
