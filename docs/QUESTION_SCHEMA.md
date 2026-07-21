# Question Schema

The canonical executable definition is `packages/question-schema/src/rigor_question_schema/models.py`. Pydantic rejects unknown fields and emits JSON Schema for TypeScript generation.

## Package boundaries

- `question.json`: prompt, instructions, dimensions, tags, objectives, prerequisites, variants, and mode-specific specification
- `solution.json`: reference and alternative solutions, trade-offs, complexity, testing, and interviewer follow-up tree
- `tests/public.json`, `tests/hidden.json`: executable cases separated by visibility
- `rubric.json`: transparent weighted dimensions
- `metadata.json`: review, validation, provenance, version, and immutable hashes

Architecture and behavioral questions use different typed mode specifications from Python and SQL exercises. Required common editorial fields remain consistent across every mode.

## Versioning

Content versions use semantic `major.minor.patch` notation. Prompt meaning or expected answer changes require a major version; substantive clarification uses minor; non-semantic editorial fixes use patch. Published submissions retain the exact content version and source hash used during evaluation.

