---
mode: ask
description: Git status as a compact lean summary — staged/unstaged counts with a pass/fail ready indicator.
---

Run git status and emit it in lean format.

Output structure:
- One line per staged file: `  + <file>` (added), `  ~ <file>` (modified), `  - <file>` (deleted), `  R <old> → <new>` (renamed)
- Summary line: `staged: N  unstaged: N  untracked: N`
- Status indicator: `✓ ready` (nothing unstaged) or `✗ unstaged changes` (has unstaged or untracked)
- Current branch: `branch: <name>` on the final line

Omit:
- "On branch" prose header
- "Changes not staged for commit" section headers
- Any line that says "nothing to commit" — express it as `staged: 0  unstaged: 0  ✓ clean`
- Suggestions ("use git add", "use git commit")
