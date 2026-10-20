# REA Paper-to-Code pilot — masked attention weights

Original, independent educational prototype for consolidated Rigor/SkillForge. **Not a production question or sandbox.**

## Task

Given rows of attention logits and equally shaped Boolean permissions masks, compute numerically stable row-wise softmax only over permitted scores. Return exact zeros for masked positions. Raise ValueError for malformed/mismatched rows, non-finite scores, non-Boolean masks or rows with no permitted key. An empty batch is allowed. Inputs must not be changed.

The learning goal is an attention-normalization micro-kernel, **not** full Transformer replication or PyTorch autograd. The mechanism is inspired by Vaswani et al., *Attention Is All You Need* (2017), arXiv:1706.03762. All code and prose here are independently authored.

## Local validation

From this directory run:

    python3 -m unittest discover -s tests -v

At intake seven local reference tests passed: an independent two-token oracle, masks and row sums, no mutation, extreme logits, excluded maximum, a single allowed key, invalid inputs and demonstration of two wrong patterns. These tests validate the local reference only, not candidate code or security isolation.

## Files

- starter.py — student-facing skeleton without solution
- reference.py — original reference, reviewer only
- tests/test_reference.py — local deterministic checks, reviewer only
- manifest.json — paper metadata, origin and pending gates
- docs/reverse-engineering/PAPERLEET_PAPER_TO_CODE_2026_10_20.md — research dossier at repository root

## Integration gate

Do **not** publish directly. Convert this original exercise to SkillForge's governed question package with rights/provenance, duplicate analysis, content version, rubric, public/hidden suites, technical/editorial review and release evidence. Candidate code must run only through the existing isolated execution plane. This local reference test suite directly imports trusted code; it is not an untrusted-code judge. A future CPU PyTorch exercise requires a reviewed sandbox image, dtype/gradient/shape tests, quotas and adversarial isolation checks.
