#!/usr/bin/env python3
"""Quick verification of preparer pipeline output."""

import json
import sys
import os
from pathlib import Path

BASE = Path(__file__).parent
ERRORS = []
WARNINGS = []


def err(msg):
    ERRORS.append(msg)
    print(f"  ❌ {msg}")


def warn(msg):
    WARNINGS.append(msg)
    print(f"  ⚠️  {msg}")


def ok(msg):
    print(f"  ✅ {msg}")


def check():
    # ── 1. Files exist ──
    print("\n=== Files ===")
    for name in ["network_docs_raw.json", "network_docs_prepared.json", "network_docs_failed.json", "network_docs_prepared_stats.json"]:
        p = BASE / name
        if p.exists():
            size = p.stat().st_size
            ok(f"{name} exists ({size / 1024:.1f} KB)")
        else:
            err(f"{name} MISSING")

    # ── 2. Load stats ──
    print("\n=== Stats Consistency ===")
    with open(BASE / "network_docs_prepared_stats.json") as f:
        stats = json.load(f)

    input_count = stats["input_count"]
    processed_count = stats["processed_count"]
    failed_count = stats["failed_count"]
    total_output = processed_count + failed_count
    
    # Q&A splitting can create more docs than input
    qa_expanded = total_output - input_count
    skipped = stats.get("dedup_removed", 0)

    ok(f"Input (raw): {input_count}")
    ok(f"Processed: {processed_count}")
    ok(f"Failed: {failed_count}")
    ok(f"Total output: {total_output}")
    if qa_expanded > 0:
        ok(f"Q&A expanded: +{qa_expanded} docs (split threads into pairs)")
    elif qa_expanded < 0:
        warn(f"Q&A expanded: {qa_expanded} (input > output)")
    ok(f"Dedup removed: {skipped}")

    # ── 3. Load documents ──
    print("\n=== Document Structure ===")
    with open(BASE / "network_docs_prepared.json") as f:
        docs = json.load(f)
    with open(BASE / "network_docs_failed.json") as f:
        failed_docs = json.load(f)

    ok(f"Prepared docs: {len(docs)}")
    ok(f"Failed docs: {len(failed_docs)}")

    if len(docs) != processed_count:
        err(f"Prepared doc count {len(docs)} != stats processed_count {processed_count}")
    else:
        ok("Count matches stats")

    if len(failed_docs) != failed_count:
        err(f"Failed doc count {len(failed_docs)} != stats failed_count {failed_count}")
    else:
        ok("Count matches stats")

    # ── 4. Required fields in prepared docs ──
    print("\n=== Prepared Doc Fields ===")
    required_meta = ["llm_quality_score", "llm_action", "content_type", "technology", "context_summary", "status"]
    missing_counts = {k: 0 for k in required_meta}
    empty_text = 0
    null_text = 0

    for i, doc in enumerate(docs):
        if "text" not in doc:
            null_text += 1
        elif not doc["text"].strip():
            empty_text += 1
        meta = doc.get("metadata", {})
        for field in required_meta:
            if field not in meta:
                missing_counts[field] += 1

    ok(f"Docs with 'text' field: {len(docs) - null_text}")
    if null_text:
        err(f"Docs missing 'text': {null_text}")
    if empty_text:
        err(f"Docs with empty text: {empty_text}")

    for field, count in missing_counts.items():
        if count > 0:
            err(f"'metadata.{field}' missing in {count} docs")
        else:
            ok(f"'metadata.{field}' present in all docs")

    # ── 5. Quality scores ──
    print("\n=== Quality Scores ===")
    scores = [d["metadata"]["llm_quality_score"] for d in docs]
    avg = sum(scores) / len(scores)
    ok(f"Average: {avg:.2f}")
    ok(f"Min: {min(scores)}, Max: {max(scores)}")
    if min(scores) < 1 or max(scores) > 10:
        err(f"Scores out of range [1,10]: min={min(scores)}, max={max(scores)}")
    else:
        ok("All scores in valid range [1,10]")

    if min(scores) < 4:
        err(f"Scores below threshold (4): min={min(scores)}")
    else:
        ok("All scores >= minimum threshold (4)")

    # ── 6. Content types ──
    print("\n=== Content Types ===")
    types = {}
    for d in docs:
        ct = d["metadata"].get("content_type", "unknown")
        types[ct] = types.get(ct, 0) + 1
    valid_types = {"troubleshooting", "reference", "theory", "configuration", "tutorial"}
    for ct, count in sorted(types.items(), key=lambda x: -x[1]):
        label = f"  {ct}: {count}"
        if ct not in valid_types:
            print(f"  ⚠️  {ct}: {count} (unexpected type)")
        else:
            print(f"  ✅ {ct}: {count}")

    # ── 7. Status distribution ──
    print("\n=== Status ===")
    statuses = {}
    for d in docs:
        s = d["metadata"].get("status", "unknown")
        statuses[s] = statuses.get(s, 0) + 1
    for s, count in sorted(statuses.items()):
        ok(f"{s}: {count}")

    # ── 8. Code blocks & syntax errors ──
    print("\n=== Code & Syntax ===")
    with_code = sum(1 for d in docs if d["metadata"].get("code_block"))
    with_errors = sum(1 for d in docs if d["metadata"].get("has_syntax_errors"))
    ok(f"Docs with code blocks: {with_code}")
    if with_errors:
        warn(f"Docs with syntax errors: {with_errors}")
    else:
        ok("No syntax errors detected")

    # ── 9. Context summaries ──
    print("\n=== Context Summaries ===")
    no_summary = sum(1 for d in docs if not d["metadata"].get("context_summary"))
    if no_summary:
        err(f"Docs missing context_summary: {no_summary}")
    else:
        ok("All docs have context_summary")

    # ── 10. Failed doc structure ──
    print("\n=== Failed Doc Structure ===")
    for i, fd in enumerate(failed_docs):
        for field in ["original_doc", "processing_error", "phase"]:
            if field not in fd:
                err(f"Failed doc {i} missing '{field}'")
    ok(f"All {len(failed_docs)} failed docs have required fields")

    # ── 11. Deduplication check ──
    print("\n=== Duplicates ===")
    hashes = [d["metadata"].get("content_hash", "") for d in docs]
    dup_hashes = [h for h in hashes if hashes.count(h) > 1]
    if dup_hashes:
        warn(f"Duplicate content hashes in prepared docs: {len(set(dup_hashes))}")
    else:
        ok("No duplicate content hashes")

    # ── Summary ──
    print("\n" + "=" * 50)
    if ERRORS:
        print(f"RESULT: {len(ERRORS)} error(s), {len(WARNINGS)} warning(s)")
        print("Issues found — review above.")
        return 1
    else:
        print("RESULT: All checks passed ✅")
        if WARNINGS:
            print(f"({len(WARNINGS)} non-critical warnings)")
        return 0


if __name__ == "__main__":
    sys.exit(check())
