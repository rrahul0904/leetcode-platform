# Source-backed question-bank recovery evidence

This document records the deterministic recovery work performed for the reviewed 11-archive source corpus. It exists to prevent future release work from silently substituting a similar public repository for an uploaded source that has not been proven equivalent.

## Authoritative reviewed corpus

The reviewed normalized corpus SHA-256 remains:

`9236110b4c4af1547455998e96f100ce5d2ba945bba1fd02d9194714a11a873b`

The reviewed manifest remains:

- archives: 11
- unique company-index questions: 3,424
- statement-backed hosted candidates: 121
- hosted candidates with reference solution: 120
- system-design resources: 29
- unique solution slugs: 1,063
- company mentions: 35,348
- source CSV rows after deduplication: 92,728

The normalized SHA is the final equality gate. Similar source trees or matching subsets are not sufficient release evidence.

## Release-grade source status: 9/11

Nine archive entries now have release-grade source/content evidence in `source-lock.json`: the three company datasets, their exact duplicate, the MIT C++ LeetCode source, the GPL pattern source, the statement source, the large multi-language solution source, and the system-design source.

Three sources that were previously retained only as `output_fingerprint_verified` were upgraded after independent pinned-Git-tree verification against the original-upload inventories:

- `LeetCode-Problem-Solution-main.zip` -> `md-shamim-ahmad/LeetCode-Problem-Solution@dab69e9cca7f78b88ac9850f1df6141b02896593`: exactly 620 files, 462 recognized code files, and 7 recognized code-language extensions; also reproduces the reviewed 121 statement-backed candidates.
- `LeetCode-Solutions-main.zip` -> `withaarzoo/LeetCode-Solutions@e3b410cb1f922dec53b63b241a8fbdb3515f619d`: exactly 2,021 recognized code files and 408 Markdown files plus 20/20 reviewed Python fingerprints. Six additional upstream blobs have quoted pseudo-extensions and are outside the corpus builder's recognized extension surface; they are documented in `PINNED_SOURCE_CONTENT_VERIFICATION.md` rather than silently treated as corpus input.
- `system-design-notes-main.zip` -> `liquidslr/system-design-notes@aa7ac69e206bca659020baa5954bb65cfd70ab99`: exactly 28 top-level chapter directories, 29 Markdown files, and 392 PNG files; also reproduces the reviewed 29 normalized resources.

The MIT C++ upload `LeetCode-Solutions-master (1).zip` remains recovered as `RajwardhanShinde/LeetCode-Solutions@3dad1af94834da381de2652d076780555130e3c6`, whose tree contains 111 useful files including 108 C++ files and MIT license evidence.

Only two source archives remain unresolved.

## Unresolved MIT JavaScript archive

Upload-derived fingerprint for `LeetCode-Solutions-master.zip`:

- 288 raw ZIP entries
- 222 useful files
- 210 code files
- MIT license
- JavaScript solution catalog/index
- README catalog with topic, difficulty, time/space complexity, and solution links

Recovery searched both current repositories and historical Git trees rather than only current HEADs.

A broad GitHub search of MIT JavaScript `LeetCode-Solutions` repositories with `master` history before the upload date scanned the plausible public set, including `yiminghe`, `DmitryNaimark`, `timothyshores`, `rishabh1403`, `alexwawl`, `manthanank`, `ifmos`, `catt-wuyang`, `Mercurius13`, and numerous smaller exact-name variants. It produced no exact 288/222/210 match.

A separate historical scan produced no partial or exact collision on the reviewed 288-entry, 222-useful, or 210-code boundaries. `DmitryNaimark/leetcode-solutions` alone was scanned across 251 unique historical trees and produced zero candidates. A current MIT + JavaScript + target-size repository search also collapses back to previously inspected repositories or forks of them.

Previously plausible catalog repositories including `kamyu104`, `apsolut-javascript`, `SHY-Corp`, `JoshCrozier`, `BaffinLee`, and `chihungyu1116` were rejected because their historical trees fail the combined useful/code fingerprint even when one boundary count matches.

Additional bounded candidates checked on 2026-08-08 also failed: `tiagogodinho/leetcode-solutions` is far below the target at roughly 21 useful / 13 code files in its strongest scanned tree, and `Jaysenso/leetcode-solutions` was scanned across 194 unique historical trees with a strongest neighborhood around 110 useful / 107 code files. `anusontarangkul/LeetCode-Solutions` was not publicly cloneable during verification and therefore cannot supply release-grade evidence.

**Conclusion:** no inspected public Git history proves an exact source identity for this uploaded archive. The lock must remain `unresolved` unless the original archive or equivalent stronger provenance evidence is supplied.

## Unresolved Competitive Programming archive

Upload-derived fingerprint for `Competitive-Programming-master.zip`:

- 470 raw ZIP entries
- 224 useful files
- 149 C++ files
- approximately 15.7 MiB archive
- algorithms, notes, and test files
- binaries and copyrighted PDFs were present in the source inventory but intentionally excluded from the useful-file count

Because 224 means useful files rather than total Git files, recovery did not accept or reject candidates solely by repository file count.

A broad public-history scan covered roughly 60 plausible C++ Competitive Programming repositories in the observed size range. A second targeted matrix compared raw archive shape, C++ count, textual/source projections, PDF counts, and extension distributions.

Representative near misses demonstrate why independent boundaries are insufficient:

- `jimgao1/competitive-programming`: a historical tree reaches 470 raw entries but has 343 C++ files; another tree reaches 149 C++ files but only 260 raw entries.
- `pranjalwalia/Competitive-programming`: a tree reaches a 224 textual projection but has 191 C++ files and a 424-entry archive shape.
- `esix/competitive-programming`: 149-C++ trees have roughly 2,600 raw entries; its 470-entry tree has only 29 C++ files.
- `Spectrum-CETB/competitive-programming`: a 149-C++ tree has 892 raw entries and the wrong useful-content profile.
- `fepaf/Competitive-Programming`: a 149-C++ tree has 1,383 raw entries and the wrong useful-content profile.
- `Aj163/Competitive-Programming`: a newly scanned historical tree gets close to the 224-useful boundary at 222 useful files, but has 206 C++ files and only 257 raw entries.
- `proRamLOGO/Competitive_Programming`: trees near the 470-entry boundary have roughly 237-241 C++ files and 285-289 useful files.
- `claytonjwong/competitive-programming`: 46 unique historical trees, zero boundary candidates.
- `anirudhakulkarni/competitive-programming`: 91 unique historical trees, zero boundary candidates.

Previously evaluated repositories such as `ashutoshm1771`, `om-ashish-soni`, `esbanarango`, `tmwilliamlin168`, `smv1999`, `kothariji`, `Manwe56`, `prasadgujar`, `luctivud`, `shiningflash`, `satyajitghana`, and `jonh14lk` also fail the reviewed combined fingerprint.

**Conclusion:** no inspected public Git history proves the original Competitive Programming archive. The lock must remain `unresolved` unless the original archive or stronger provenance evidence is supplied.

## Exact corpus payload recovery

The repository history was checked for `content/imported/source-backed/question-bank.zip.b64`; no reachable commit contains it. Retained GitHub Actions artifacts were also checked and do not contain the reviewed normalized bank. Exact-name and upload-window File Library recovery found analysis/fingerprint records rather than reusable original ZIP objects.

The checked-in `content/question-bank-manifest.json` describes the separate canonical publication set (423 published packages), not the reviewed 3,425-question source-bank payload. The split files under `content/imported/source-backed` contain only quarantined Python review material. Neither can be repurposed as the missing normalized corpus.

Therefore the exact reviewed normalized payload cannot be recovered from current repository history, retained CI artifacts, or retained File Library objects.

## Publication / execution boundary

The 20 source-backed Python review packages reproduce the reviewed Python fingerprints from `withaarzoo/LeetCode-Solutions` at the pinned source revision. That pinned revision does not contain compatible license evidence for Rigor hosting/redistribution, so these packages remain `rights_review_required` and quarantined outside the canonical publication tree.

They must not be promoted merely to satisfy a Run -> Submit release gate. A source-backed executable Python vertical slice requires explicit compatible rights evidence/approval or an independently authored/licensed replacement package with transparent provenance and publication metadata.

## Release consequence

`make release-check` is intentionally fail-closed while either of the two source entries remains unresolved. This is the correct behavior.

Everything independent of the missing source bytes remains testable through normal CI, Content Validation, Local Docker release, and the pinned-source provenance workflow. Full source-bank technical release readiness requires one of these evidence paths:

1. the original `LeetCode-Solutions-master.zip` and `Competitive-Programming-master.zip`, followed by deterministic reconstruction and exact normalized SHA verification; or
2. the exact reviewed normalized corpus ZIP whose SHA-256 is `9236110b4c4af1547455998e96f100ce5d2ba945bba1fd02d9194714a11a873b`.

Executable publication of the source-backed Python review material additionally requires compatible rights approval/evidence.
