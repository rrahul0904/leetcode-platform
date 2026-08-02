# Uploaded Interview Corpus Inventory

Verified from the user-provided archives on 2026-08-01.

The archives are offline import sources. The live application reads normalized PostgreSQL records and never reads ZIP files or extracted directories at runtime.

| Archive | Compressed size | Files | Main useful content | Import disposition |
| --- | ---: | ---: | --- | --- |
| `LeetCode-Problem-Solution-main.zip` | 2.31 MiB | 2,203 | Numbered problem folders, Markdown descriptions, C++/Java/C#/Python/JavaScript/Go/Dart solutions | Rights review required |
| `LeetCode-Solutions-main.zip` | 3.98 MiB | 2,876 | Numbered questions, 408 explanations, multi-language code with especially strong Python and JavaScript coverage | Rights review required |
| `LeetCode-Solutions-master (1).zip` | 1.04 MiB | 334 | MIT-licensed C++ solution catalog and complexity metadata | Hostable licensed, review required before publication |
| `LeetCode-Solutions-master.zip` | 534 KiB | 288 | MIT-licensed JavaScript solution catalog and index | Hostable licensed, review required before publication |
| `Competitive-Programming-master.zip` | 15.7 MiB | 470 | Algorithms, dynamic programming, graphs, segment trees, strings, number theory, and advanced practice resources | Rights review required; binaries and PDFs quarantined |
| `leetcode-company-wise-problems-main.zip` | 826 KiB | 132 | Company CSVs with title, difficulty, frequency, acceptance, URLs, and topics | External-reference metadata only |
| `leetcode-company-wise-problems-main (1).zip` | 826 KiB | 132 | Exact byte-for-byte duplicate of the previous archive | Skipped as exact duplicate |
| `leetcode-companywise-interview-questions-master.zip` | 483 KiB | 403 | Company/time-window CSV observations | External-reference metadata only |
| `LeetCode-Questions-CompanyWise-master.zip` | 2.52 MiB | 3,611 | Large company/time-window CSV corpus | External-reference metadata only |
| `awesome-leetcode-resources-main.zip` | 530 KiB | 108 | Pattern-oriented solutions across several languages | Rights review required; GPL obligations remain explicit |
| `system-design-notes-main.zip` | 72.7 MiB | 427 | 29 Markdown chapters and 392 diagrams/images | Rights review required; coverage map until approved |

## Exact duplicate

The following two archives share the same SHA-256 digest and are processed once:

```text
leetcode-company-wise-problems-main.zip
leetcode-company-wise-problems-main (1).zip
```

## Primary launch focus

1. Python coding problems and reviewed Python approaches.
2. JavaScript coding problems and reviewed JavaScript approaches.
3. Original PostgreSQL question generation because the uploaded corpus contains little structured SQL practice content.
4. System-design concepts, study paths, and independently reviewed Rigor practice scenarios.
5. Company observations connected to canonical problem identities rather than duplicated problem records.

## Reproducible import

```bash
uv run python scripts/knowledge_bank.py build-corpus \
  /path/to/uploaded-archives \
  .work/knowledge-bank \
  --clean \
  --disposition-map config/knowledge-source-dispositions.json \
  --output .work/knowledge-bank/corpus.json

uv run python scripts/knowledge_bank.py import \
  .work/knowledge-bank/corpus.json \
  --dry-run

uv run python scripts/knowledge_bank.py import \
  .work/knowledge-bank/corpus.json
```

The import is idempotent by archive hash, source file hash, canonical problem identity, solution hash, and company observation identity.
