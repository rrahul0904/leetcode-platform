# Pinned source content verification

This document records release-grade source-content evidence for pinned upstream revisions whose original ZIP packaging bytes are not retained.

The release contract permits `exact_content_fingerprint_verified` when the pinned source revision reproduces the reviewed builder-relevant content fingerprint. This does **not** claim byte-identical GitHub ZIP packaging.

## Statement source

Archive: `LeetCode-Problem-Solution-main.zip`

Pinned revision: `md-shamim-ahmad/LeetCode-Problem-Solution@dab69e9cca7f78b88ac9850f1df6141b02896593`

Original-upload inventory:

- 620 files
- 462 recognized code files
- 7 recognized code-language extensions

Independent pinned-tree verification reproduces all three counts exactly. The same locked source also reproduces the reviewed 121 statement-backed candidates.

## Multi-language solution source

Archive: `LeetCode-Solutions-main.zip`

Pinned revision: `withaarzoo/LeetCode-Solutions@e3b410cb1f922dec53b63b241a8fbdb3515f619d`

Original-upload builder-relevant inventory:

- 2,021 recognized code files
- 408 Markdown files
- 20 reviewed Python fingerprints

Independent pinned-tree verification reproduces the 2,021 code and 408 Markdown counts exactly, and reconstruction reproduces 20/20 reviewed Python fingerprints.

The pinned Git tree contains six additional oddly named blobs ending in quoted pseudo-extensions: `.cpp"`, `.go"`, `.java"`, `.js"`, `.md"`, and `.py"`. `scripts/build_uploaded_question_bank.py` recognizes none of those pseudo-extensions, so they are outside the normalized corpus input surface. They are retained as provenance evidence rather than silently counted as source content.

## System-design source

Archive: `system-design-notes-main.zip`

Pinned revision: `liquidslr/system-design-notes@aa7ac69e206bca659020baa5954bb65cfd70ab99`

Original-upload inventory:

- 28 chapter directories
- 29 Markdown files
- 392 PNG files

Independent pinned-tree verification reproduces all three counts exactly. The locked source also reproduces the reviewed 29 normalized system-design resources.

## Automation

`.github/workflows/source-provenance.yml` checks these pinned revisions on every pull request using `scripts/verify_pinned_source_content.py` and explicitly checks out the exact PR head SHA.
