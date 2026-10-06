#!/usr/bin/env python3
"""
Comprehensive Duplicate File Scanner for G:\ drive.
Compatible with Python 3.5+.
"""

import os
import sys
import json
import hashlib
import time
from collections import defaultdict
from datetime import datetime

# --- Configuration ---
ROOT_PATH = sys.argv[1] if len(sys.argv) > 1 else "G:\\"
REPORT_DIR = os.path.join(ROOT_PATH, "__duplicate_scanner")
JSON_REPORT = os.path.join(REPORT_DIR, "duplicates_report.json")
TEXT_REPORT = os.path.join(REPORT_DIR, "duplicates_summary.txt")
MIN_FILE_SIZE = 1  # Skip 0-byte files
HASH_CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB

SKIP_DIRS = {
    "$RECYCLE.BIN",
    "System Volume Information",
    "__duplicate_scanner",
}


def human_size(nbytes):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(nbytes) < 1024.0:
            return "{:.2f} {}".format(nbytes, unit)
        nbytes /= 1024.0
    return "{:.2f} PB".format(nbytes)


def sha256_file(filepath):
    h = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(HASH_CHUNK_SIZE)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except (PermissionError, OSError):
        return None


def scan_all_files(root):
    all_files = []
    error_paths = []
    scanned_dirs = 0
    scanned_files = 0

    print("")
    print("=" * 70)
    print("  PHASE 1: Scanning all files under {}".format(root))
    print("=" * 70)
    print("")

    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        scanned_dirs += 1

        if scanned_dirs % 50 == 0:
            print("  [Scan] Processed {} directories, {} files so far...".format(scanned_dirs, scanned_files))

        for fname in filenames:
            fpath = os.path.join(dirpath, fname)
            scanned_files += 1
            try:
                stat = os.stat(fpath)
                fsize = stat.st_size
                if fsize >= MIN_FILE_SIZE:
                    all_files.append({
                        "path": fpath,
                        "size": fsize,
                        "mtime": stat.st_mtime,
                    })
            except (PermissionError, OSError) as e:
                error_paths.append({"path": fpath, "error": str(e)})

    print("")
    print("  [Scan Complete] {} directories, {} files found.".format(scanned_dirs, scanned_files))
    print("  [Scan Complete] {} readable files (>= {} byte).".format(len(all_files), MIN_FILE_SIZE))
    if error_paths:
        print("  [Scan Complete] {} files could not be read.".format(len(error_paths)))

    return all_files, error_paths


def group_by_size(all_files):
    print("")
    print("=" * 70)
    print("  PHASE 2: Grouping by file size (fast pre-filter)")
    print("=" * 70)
    print("")

    size_groups = defaultdict(list)
    for f in all_files:
        size_groups[f["size"]].append(f)

    candidates = {sz: files for sz, files in size_groups.items() if len(files) >= 2}

    total_candidates = sum(len(v) for v in candidates.values())
    print("  [Size Filter] {} size groups with potential duplicates.".format(len(candidates)))
    print("  [Size Filter] {} files need hashing.".format(total_candidates))
    print("")

    return candidates


def hash_candidates(size_groups):
    print("=" * 70)
    print("  PHASE 3: Computing SHA-256 hashes to confirm duplicates")
    print("=" * 70)
    print("")

    hash_groups = defaultdict(list)
    total_to_hash = sum(len(v) for v in size_groups.values())
    hashed = 0
    hash_errors = 0

    for size in sorted(size_groups.keys(), reverse=True):
        files = size_groups[size]
        for f in files:
            hashed += 1
            if hashed % 100 == 0:
                print("  [Hash] {}/{} files hashed...".format(hashed, total_to_hash))

            file_hash = sha256_file(f["path"])
            if file_hash:
                key = "{}_{}".format(file_hash, size)
                hash_groups[key].append(f)
            else:
                hash_errors += 1

    duplicates = {k: v for k, v in hash_groups.items() if len(v) >= 2}

    total_dup_files = sum(len(v) for v in duplicates.values())
    print("")
    print("  [Hash Complete] {} files hashed, {} errors.".format(hashed, hash_errors))
    print("  [Hash Complete] {} duplicate groups found ({} files total).".format(len(duplicates), total_dup_files))

    return duplicates


def build_report(duplicates, error_paths, scan_time):
    groups = []
    total_wasted = 0

    # Sort by file size descending
    sorted_keys = sorted(duplicates.keys(), key=lambda k: -duplicates[k][0]["size"])

    for key in sorted_keys:
        files = duplicates[key]
        size = files[0]["size"]
        wasted = size * (len(files) - 1)
        total_wasted += wasted

        files_sorted = sorted(files, key=lambda f: f["mtime"])

        group = {
            "hash": key.split("_")[0],
            "file_size": size,
            "file_size_human": human_size(size),
            "count": len(files),
            "wasted_bytes": wasted,
            "wasted_human": human_size(wasted),
            "files": [
                {
                    "path": f["path"],
                    "modified": datetime.fromtimestamp(f["mtime"]).strftime("%Y-%m-%d %H:%M:%S"),
                    "is_oldest": (i == 0),
                }
                for i, f in enumerate(files_sorted)
            ],
        }
        groups.append(group)

    report = {
        "scan_root": ROOT_PATH,
        "scan_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "scan_duration_seconds": round(scan_time, 2),
        "total_duplicate_groups": len(groups),
        "total_duplicate_files": sum(g["count"] for g in groups),
        "total_wasted_bytes": total_wasted,
        "total_wasted_human": human_size(total_wasted),
        "duplicate_groups": groups,
        "errors": error_paths[:100],
    }

    return report


def write_text_summary(report):
    lines = []
    lines.append("=" * 80)
    lines.append("  DUPLICATE FILE ANALYSIS REPORT")
    lines.append("  Scanned: {}".format(report["scan_root"]))
    lines.append("  Date: {}".format(report["scan_date"]))
    lines.append("  Duration: {}s".format(report["scan_duration_seconds"]))
    lines.append("=" * 80)
    lines.append("")
    lines.append("  TOTAL DUPLICATE GROUPS:  {}".format(report["total_duplicate_groups"]))
    lines.append("  TOTAL DUPLICATE FILES:   {}".format(report["total_duplicate_files"]))
    lines.append("  TOTAL WASTED SPACE:      {} ({:,} bytes)".format(
        report["total_wasted_human"], report["total_wasted_bytes"]))
    lines.append("")
    lines.append("-" * 80)

    for i, group in enumerate(report["duplicate_groups"], 1):
        lines.append("")
        lines.append("  GROUP {}: {} copies | {} each | {} wasted".format(
            i, group["count"], group["file_size_human"], group["wasted_human"]))
        lines.append("  Hash: {}...".format(group["hash"][:16]))
        for f in group["files"]:
            marker = " [OLDEST]" if f["is_oldest"] else ""
            lines.append("    -> {}{}".format(f["path"], marker))
            lines.append("       Modified: {}".format(f["modified"]))
        lines.append("-" * 80)

    lines.append("")
    lines.append("=" * 80)
    lines.append("  TOP 20 BIGGEST SPACE WASTERS")
    lines.append("=" * 80)
    for i, group in enumerate(report["duplicate_groups"][:20], 1):
        lines.append("  {:3d}. {:>12s} wasted | {} copies of {} file".format(
            i, group["wasted_human"], group["count"], group["file_size_human"]))
        lines.append("       Example: {}".format(group["files"][0]["path"]))

    if report["errors"]:
        lines.append("")
        lines.append("  NOTE: {} files could not be read (permission errors).".format(len(report["errors"])))

    return "\n".join(lines)


def main():
    print("")
    print("  Duplicate File Scanner")
    print("  Target: {}".format(ROOT_PATH))
    print("  Started: {}".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    print("")

    os.makedirs(REPORT_DIR, exist_ok=True)

    t0 = time.time()

    all_files, error_paths = scan_all_files(ROOT_PATH)
    size_groups = group_by_size(all_files)
    duplicates = hash_candidates(size_groups)

    scan_time = time.time() - t0

    report = build_report(duplicates, error_paths, scan_time)

    with open(JSON_REPORT, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print("")
    print("  JSON report saved: {}".format(JSON_REPORT))

    text = write_text_summary(report)
    with open(TEXT_REPORT, "w") as f:
        f.write(text)
    print("  Text summary saved: {}".format(TEXT_REPORT))

    print("")
    print("=" * 70)
    print("  RESULTS SUMMARY")
    print("=" * 70)
    print("  Duplicate groups found:  {}".format(report["total_duplicate_groups"]))
    print("  Total duplicate files:   {}".format(report["total_duplicate_files"]))
    print("  Total wasted space:      {}".format(report["total_wasted_human"]))
    print("  Scan duration:           {}s".format(report["scan_duration_seconds"]))
    print("=" * 70)
    print("")


if __name__ == "__main__":
    main()
