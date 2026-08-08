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

## Resolved sources

The source lock contains exact content-fingerprint matches for the three company datasets, the duplicate company archive, the MIT C++ LeetCode source, and the GPL pattern source. Output-level fingerprints are also retained for the statement source, the large multi-language solution source, and system-design notes.

The MIT C++ upload `LeetCode-Solutions-master (1).zip` was recovered as `RajwardhanShinde/LeetCode-Solutions` at commit `3dad1af94834da381de2652d076780555130e3c6`. Its tree contains 111 files: 108 C++ files plus README, license, and config, matching the reviewed useful-content fingerprint.

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

A separate 15-repository parallel historical scan also produced no partial or exact collision on the reviewed 288-entry, 222-useful, or 210-code boundaries. `DmitryNaimark/leetcode-solutions` alone was scanned across 251 unique historical trees and produced zero candidates.

Previously plausible catalog repositories including `kamyu104`, `apsolut-javascript`, `SHY-Corp`, `JoshCrozier`, `BaffinLee`, and `chihungyu1116` were also rejected because their historical trees fail the combined useful/code fingerprint even when one boundary count matches.

**Conclusion:** no public Git history inspected during recovery proves an exact source identity for this uploaded archive. The lock must remain `unresolved` unless the original archive or equivalent stronger provenance evidence is supplied.

## Unresolved Competitive Programming archive

Upload-derived fingerprint for `Competitive-Programming-master.zip`:

- 470 raw ZIP entries
- 224 useful files
- 149 C++ files
- approximately 15.7 MiB archive
- algorithms, notes, and test files
- binaries and copyrighted PDFs were present in the source inventory but intentionally excluded from the useful-file count

Because 224 means useful files rather than total Git files, recovery did not accept or reject candidates solely by repository file count.

A broad public-history scan covered roughly 60 plausible C++ Competitive Programming repositories in the observed size range. A second targeted 15-repository matrix compared raw archive shape, C++ count, textual/source projections, PDF counts, and extension distributions.

Representative near misses demonstrate why independent boundaries are insufficient:

- `jimgao1/competitive-programming`: a historical tree reaches 470 raw entries but has 343 C++ files; another tree reaches 149 C++ files but only 260 raw entries.
- `pranjalwalia/Competitive-programming`: a tree reaches a 224 textual projection but has 191 C++ files and a 424-entry archive shape.
- `esix/competitive-programming`: 149-C++ trees have roughly 2,600 raw entries; its 470-entry tree has only 29 C++ files.
- `Spectrum-CETB/competitive-programming`: a 149-C++ tree has 892 raw entries and the wrong useful-content profile.
- `fepaf/Competitive-Programming`: a 149-C++ tree has 1,383 raw entries and the wrong useful-content profile.
- `claytonjwong/competitive-programming`: 46 unique historical trees, zero boundary candidates.
- `anirudhakulkarni/competitive-programming`: 91 unique historical trees, zero boundary candidates.

Previously evaluated repositories such as `ashutoshm1771`, `om-ashish-soni`, `esbanarango`, `tmwilliamlin168`, `smv1999`, `kothariji`, `Manwe56`, `prasadgujar`, `luctivud`, `shiningflash`, `satyajitghana`, and `jonh14lk` also fail the reviewed combined fingerprint.

**Conclusion:** no inspected public Git history proves the original Competitive Programming archive. The lock must remain `unresolved` unless the original archive or stronger provenance evidence is supplied.

## Exact corpus payload recovery

The repository history was checked for `content/imported/source-backed/question-bank.zip.b64`; no reachable commit contains it. Retained GitHub Actions artifacts were also checked and do not contain the reviewed normalized bank. The available File Library material preserves the upload analysis/fingerprints but does not expose the original ZIP objects as reusable source bytes.

Therefore the exact reviewed normalized payload cannot be recovered from current repository history or retained CI artifacts.

## Publication / execution boundary

The 20 source-backed Python review packages reproduce the reviewed Python fingerprints from `withaarzoo/LeetCode-Solutions` at the pinned source revision. That pinned revision does not contain a license file, so these packages remain `rights_review_required` and quarantined outside the canonical publication tree.

They must not be promoted merely to satisfy a Run -> Submit release gate. A source-backed executable Python vertical slice requires explicit compatible rights evidence or an independently authored/licensed replacement package.

## Release consequence

`make release-check` is intentionally fail-closed while the source lock contains unresolved or non-release-grade entries. This is the correct behavior.

Everything that can be validated independently of the missing source bytes remains testable through normal CI, Content Validation, and Local Docker release workflows. Full source-bank release readiness requires one of these evidence paths:

1. the original `LeetCode-Solutions-master.zip` and `Competitive-Programming-master.zip`, followed by deterministic reconstruction and exact normalized SHA verification; or
2. the exact reviewed normalized corpus ZIP whose SHA-256 is `9236110b4c4af1547455998e96f100ce5d2ba945bba1fd02d9194714a11a873b`.

Executable publication of the source-backed Python review material additionally requires compatible rights approval/evidence.
