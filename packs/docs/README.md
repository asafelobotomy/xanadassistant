# docs pack

The docs pack installs documentation-first defaults — Diátaxis-aware drafting,
API doc conventions, prose style guidance, and Markdown link validation — so
that documentation stays complete and accurate as the codebase evolves.

## Purpose

Install this pack when documentation is a first-class deliverable. Agents will
flag missing public API docs as blocking issues, document inline rather than
leaving TODO placeholders, and match the register of the surrounding doc corpus.

## Surfaces

| Surface | Contents |
|---|---|
| **Skills** | `docsApi`, `docsReview`, `docsStructure`, `docsStyle` |
| **Prompts** | `/docs-draft`, `/docs-review` |
| **MCP** | `docsLinkCheck.py` — validates Markdown links and surfaces broken references |

## Token overrides

| Token | Docs behavior |
|---|---|
| `{{pack:review-depth}}` | Flag missing documentation for any public API, CLI flag, or user-visible behavior change as a blocking issue |
| `{{pack:output-style}}` | Match the register of the surrounding doc corpus; prefer short sentences, active voice, and imperative mood for instructions |
| `{{pack:scope-discipline}}` | Document public API and behavior changes inline; ask for missing information rather than guessing |

## Interview customization

During setup you can choose the structure framework for new documentation:

- **Corpus match** (default) — match the heading depth, terminology, and
  code-example style of the surrounding documentation.
- **Diátaxis** — organize new docs by type: tutorials (learning-oriented),
  how-to guides (task-oriented), reference (information-oriented), and
  explanations (understanding-oriented). No mixing types within one document.

Both options override `{{pack:output-style}}`.
