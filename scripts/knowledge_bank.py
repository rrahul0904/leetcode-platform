#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import asdict
from pathlib import Path

from rigor_api.knowledge_ingestion import (
    SourceDisposition,
    extract_archive,
    inventory_archives,
    merge_bundles,
    parse_repository,
    write_json,
)


def disposition(value: str) -> SourceDisposition:
    try:
        return SourceDisposition(value)
    except ValueError as exc:
        choices = ", ".join(item.value for item in SourceDisposition)
        raise argparse.ArgumentTypeError(f"Disposition must be one of: {choices}") from exc


def inventory_command(args: argparse.Namespace) -> int:
    records = inventory_archives(args.directory)
    payload = [asdict(record) for record in records]
    if args.output:
        write_json(args.output, payload)
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    duplicates = sum(record.duplicate_of is not None for record in records)
    print(f"Inventoried {len(records)} archives; exact duplicates: {duplicates}")
    return 0


def extract_command(args: argparse.Namespace) -> int:
    inventory = extract_archive(args.archive, args.destination)
    print(json.dumps(asdict(inventory), indent=2, sort_keys=True))
    return 0


def scan_command(args: argparse.Namespace) -> int:
    bundle = parse_repository(
        args.repository,
        source_name=args.source_name or args.repository.name,
        disposition=args.disposition,
    )
    write_json(args.output, bundle.to_dict())
    print(json.dumps(bundle.to_dict()["counts"], indent=2, sort_keys=True))
    return 0


def corpus_command(args: argparse.Namespace) -> int:
    workspace = args.workspace
    if args.clean and workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    extracted = workspace / "extracted"
    reports = workspace / "reports"
    extracted.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)

    inventories = inventory_archives(args.archives)
    write_json(reports / "archive-inventory.json", [asdict(item) for item in inventories])

    bundles = []
    processed_hashes: set[str] = set()
    for archive in inventories:
        if archive.archive_sha256 in processed_hashes:
            continue
        processed_hashes.add(archive.archive_sha256)
        archive_path = args.archives / archive.archive_name
        target = extracted / archive.archive_name.removesuffix(".zip")
        extract_archive(archive_path, target)
        roots = [item for item in target.iterdir() if item.is_dir()]
        repository_root = roots[0] if len(roots) == 1 else target
        source_disposition = args.disposition
        bundle = parse_repository(
            repository_root,
            source_name=archive.archive_name.removesuffix(".zip"),
            disposition=source_disposition,
        )
        bundles.append(bundle)
        write_json(reports / f"{archive.archive_sha256}.json", bundle.to_dict())

    merged = merge_bundles(bundles)
    write_json(args.output, merged.to_dict())
    print(json.dumps(merged.to_dict()["counts"], indent=2, sort_keys=True))
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Build Rigor knowledge-bank staging records from offline source archives."
    )
    commands = root.add_subparsers(dest="command", required=True)

    inventory = commands.add_parser("inventory", help="Inventory ZIP archives and exact duplicates")
    inventory.add_argument("directory", type=Path)
    inventory.add_argument("--output", type=Path)
    inventory.set_defaults(handler=inventory_command)

    extract = commands.add_parser("extract", help="Safely extract one ZIP archive")
    extract.add_argument("archive", type=Path)
    extract.add_argument("destination", type=Path)
    extract.set_defaults(handler=extract_command)

    scan = commands.add_parser("scan", help="Parse an extracted repository")
    scan.add_argument("repository", type=Path)
    scan.add_argument("--source-name")
    scan.add_argument(
        "--disposition",
        type=disposition,
        default=SourceDisposition.RIGHTS_REVIEW_REQUIRED,
    )
    scan.add_argument("--output", type=Path, required=True)
    scan.set_defaults(handler=scan_command)

    corpus = commands.add_parser(
        "build-corpus",
        help="Inventory, extract, parse, deduplicate, and emit one staging corpus",
    )
    corpus.add_argument("archives", type=Path)
    corpus.add_argument("workspace", type=Path)
    corpus.add_argument("--output", type=Path, required=True)
    corpus.add_argument("--clean", action="store_true")
    corpus.add_argument(
        "--disposition",
        type=disposition,
        default=SourceDisposition.RIGHTS_REVIEW_REQUIRED,
    )
    corpus.set_defaults(handler=corpus_command)
    return root


def main() -> int:
    args = parser().parse_args()
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
