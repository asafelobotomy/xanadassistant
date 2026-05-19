"""One-off script: add ## When to use, ## When NOT to use, ## Verify to pack SKILL.md files."""

import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.add_skill_sections_data_a import ADDITIONS as ADDITIONS_A
from scripts.add_skill_sections_data_b import ADDITIONS as ADDITIONS_B


REPO = str(REPO_ROOT)
ADDITIONS = ADDITIONS_A | ADDITIONS_B


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
