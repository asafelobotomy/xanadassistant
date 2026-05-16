---
name: ossLicensing
description: "OSS license guidance — choosing a license, LICENSE file format, SPDX identifiers, and header placement."
---

# ossLicensing

Use this skill when a user asks about OSS licensing: what license to choose, how to add a LICENSE file, how to check license compatibility, or how to use SPDX identifiers correctly.

## License selection guide

| License | Permissions | Copyleft | Use when |
|---|---|---|---|
| MIT | Broad | None | Maximum permissive; fewest restrictions on users |
| Apache 2.0 | Broad + patent grant | None | Enterprise-friendly; explicit patent protection |
| GPL-3.0 | Broad | Strong (derivative works) | Force derivatives to stay open |
| LGPL-3.0 | Broad | Weak (library boundary) | Library that may be used in proprietary apps |
| MPL-2.0 | Broad | File-level | Per-file copyleft; compatible with Apache 2.0 |
| ISC | Broad | None | Functionally equivalent to MIT; fewer words |
| AGPL-3.0 | Broad | Network-use copyleft | SaaS: require source disclosure even for hosted use |

**Compatibility note**: Apache-2.0 code can be included in a GPL-3.0 project, but GPL-3.0 code cannot be redistributed under Apache-2.0 terms. If a project mixes licenses, verify the redistribution path for the combined work and escalate to counsel for organization-specific policy.

## LICENSE file

- Place `LICENSE` (no extension) in the repository root.
- Use the full plain-text body from https://spdx.org/licenses/ — do not abbreviate.
- Update the copyright year and holder at the top.

Example header:
```
MIT License

Copyright (c) 2024 Example Author

Permission is hereby granted...
```

## SPDX identifiers

Add an SPDX identifier to source file headers only when the repository's policy, existing conventions, or contributor requirements call for per-file licensing metadata:

```python
# SPDX-License-Identifier: MIT
```

```typescript
// SPDX-License-Identifier: Apache-2.0
```

The identifier must match the SPDX license list exactly: https://spdx.org/licenses/

## Multi-license projects

When a project contains files under different licenses:

1. Use SPDX identifiers in each file if the repository already uses per-file license metadata or explicitly requires it.
2. Add a `LICENSES/` directory containing the full text of each license used.
3. Reference all licenses in the root `README.md` under a **License** section.

## Dependency license audit

Before releasing, verify that all dependencies have compatible licenses:

```bash
# Node.js
npx license-checker --onlyAllow "MIT;ISC;Apache-2.0;BSD-2-Clause;BSD-3-Clause"

# Python
pip install pip-licenses && pip-licenses --order=license
```

Flag any GPL or AGPL dependency in a library project — it may require the entire project to be GPL.
