#!/usr/bin/env python3
"""
Deep Duplicate Scanner Framework v2.0
======================================
Comprehensive multi-phase duplicate & redundancy analysis for entire drives.
Outputs a rich JSON report consumed by the interactive HTML dashboard.

Phases:
  1. Full recursive file index (every file, every subfolder)
  2. Size-based pre-filter (fast grouping)
  3. Partial hash (first+last 4KB) for quick dedup
  4. Full SHA-256 for confirmed duplicates
  5. Category & extension breakdown
  6. Folder-level duplication analysis
  7. Near-duplicate filename detection
  8. Empty folder & tiny file detection
  9. Report generation (JSON + text summary)
"""

import os
import sys
import json
import hashlib
import time
import re
from collections import defaultdict
from datetime import datetime
from difflib import SequenceMatcher

# ═══════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

ROOT_PATH = sys.argv[1] if len(sys.argv) > 1 else "G:\\"
REPORT_DIR = os.path.join(ROOT_PATH, "__duplicate_scanner")
JSON_REPORT = os.path.join(REPORT_DIR, "deep_scan_report.json")
TEXT_REPORT = os.path.join(REPORT_DIR, "deep_scan_summary.txt")

MIN_FILE_SIZE = 1          # Skip 0-byte files for duplicate check
HASH_CHUNK = 8 * 1024 * 1024  # 8 MB chunks for full hash
PARTIAL_HASH_SIZE = 4096   # 4 KB for partial hash (head + tail)
NEAR_DUP_THRESHOLD = 0.85  # Filename similarity threshold
TINY_FILE_THRESHOLD = 1024 # Files <= 1KB considered "tiny"

SKIP_DIRS = {
    "$RECYCLE.BIN",
    "System Volume Information",
    "__duplicate_scanner",
    ".Trash-1000",
}

# File category mapping
CATEGORY_MAP = {
    "Video": {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".mpg", ".mpeg", ".3gp", ".ts"},
    "Audio": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a", ".opus"},
    "Image": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".svg", ".webp", ".ico", ".raw", ".cr2", ".nef"},
    "Document": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods", ".odp", ".rtf", ".txt", ".csv", ".tex"},
    "Archive": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso", ".dmg"},
    "Code": {".py", ".js", ".ts", ".html", ".css", ".java", ".c", ".cpp", ".h", ".hpp", ".cs", ".go", ".rs", ".rb", ".php", ".sh", ".bat", ".ps1", ".json", ".xml", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".md", ".rst"},
    "Executable": {".exe", ".msi", ".dll", ".so", ".app", ".apk", ".deb", ".rpm"},
    "Database": {".db", ".sqlite", ".sql", ".mdb", ".accdb"},
    "Science": {".pdb", ".mol", ".mol2", ".sdf", ".cif", ".fasta", ".fa", ".fna", ".chk", ".log", ".gjf", ".com", ".out", ".cube", ".wfn", ".fchk"},
}

def get_category(ext):
    ext = ext.lower()
    for cat, exts in CATEGORY_MAP.items():
        if ext in exts:
            return cat
    return "Other"


# ═══════════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════════

def human_size(nbytes):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(nbytes) < 1024.0:
            return "{:.2f} {}".format(nbytes, unit)
        nbytes /= 1024.0
    return "{:.2f} PB".format(nbytes)


def partial_hash(filepath, size):
    """Hash first 4KB + last 4KB for fast pre-filter."""
    try:
        h = hashlib.md5()
        with open(filepath, "rb") as f:
            head = f.read(PARTIAL_HASH_SIZE)
            h.update(head)
            if size > PARTIAL_HASH_SIZE * 2:
                f.seek(-PARTIAL_HASH_SIZE, 2)
                tail = f.read(PARTIAL_HASH_SIZE)
                h.update(tail)
        return h.hexdigest()
    except (PermissionError, OSError):
        return None


def full_hash(filepath):
    """Full SHA-256 hash."""
    h = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(HASH_CHUNK)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except (PermissionError, OSError):
        return None


def normalize_filename(name):
    """Strip common copy suffixes like (1), (2), Copy of, - Copy, etc."""
    name = re.sub(r'\s*\(\d+\)\s*', '', name)
    name = re.sub(r'\s*-\s*Copy\s*', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\bCopy\s+of\s+', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*\[\d+\]\s*', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name.lower()


# ═══════════════════════════════════════════════════════════════════
# PHASE 1: Full recursive file index
# ═══════════════════════════════════════════════════════════════════

def phase1_index(root):
    print("\n" + "=" * 74)
    print("  PHASE 1: Full recursive file index")
    print("  Target: {}".format(root))
    print("=" * 74 + "\n")

    all_files = []
    all_dirs = []
    error_paths = []
    total_size = 0
    dir_count = 0
    file_count = 0

    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        dir_count += 1
        all_dirs.append(dirpath)

        if dir_count % 100 == 0:
            print("  [Index] {} dirs, {} files, {} indexed...".format(dir_count, file_count, len(all_files)))

        for fname in filenames:
            fpath = os.path.join(dirpath, fname)
            file_count += 1
            try:
                stat = os.stat(fpath)
                fsize = stat.st_size
                ext = os.path.splitext(fname)[1]
                total_size += fsize
                entry = {
                    "path": fpath,
                    "name": fname,
                    "ext": ext.lower(),
                    "size": fsize,
                    "mtime": stat.st_mtime,
                    "dir": dirpath,
                    "category": get_category(ext),
                }
                all_files.append(entry)
            except (PermissionError, OSError) as e:
                error_paths.append({"path": fpath, "error": str(e)})

    print("\n  [Phase 1 Complete]")
    print("    Directories scanned:  {:,}".format(dir_count))
    print("    Files found:          {:,}".format(file_count))
    print("    Indexable files:      {:,}".format(len(all_files)))
    print("    Total size:           {}".format(human_size(total_size)))
    print("    Errors:               {:,}".format(len(error_paths)))

    return all_files, all_dirs, error_paths, total_size


# ═══════════════════════════════════════════════════════════════════
# PHASE 2: Size grouping
# ═══════════════════════════════════════════════════════════════════

def phase2_size_group(all_files):
    print("\n" + "=" * 74)
    print("  PHASE 2: Size-based pre-filter")
    print("=" * 74 + "\n")

    size_map = defaultdict(list)
    for f in all_files:
        if f["size"] >= MIN_FILE_SIZE:
            size_map[f["size"]].append(f)

    candidates = {s: files for s, files in size_map.items() if len(files) >= 2}
    n_cand = sum(len(v) for v in candidates.values())
    unique = len(size_map) - len(candidates)

    print("  Unique sizes (no dups):   {:,}".format(unique))
    print("  Candidate size groups:    {:,}".format(len(candidates)))
    print("  Files to hash:            {:,}".format(n_cand))

    return candidates


# ═══════════════════════════════════════════════════════════════════
# PHASE 3: Partial hash (fast dedup)
# ═══════════════════════════════════════════════════════════════════

def phase3_partial_hash(size_groups):
    print("\n" + "=" * 74)
    print("  PHASE 3: Partial hash (head+tail 4KB) fast filter")
    print("=" * 74 + "\n")

    partial_map = defaultdict(list)
    total = sum(len(v) for v in size_groups.values())
    done = 0
    errors = 0

    for size, files in sorted(size_groups.items(), reverse=True):
        for f in files:
            done += 1
            if done % 200 == 0:
                print("  [Partial] {}/{} ...".format(done, total))
            ph = partial_hash(f["path"], f["size"])
            if ph:
                key = "{}_{}".format(ph, size)
                partial_map[key].append(f)
            else:
                errors += 1

    candidates = {k: v for k, v in partial_map.items() if len(v) >= 2}
    n_cand = sum(len(v) for v in candidates.values())

    print("\n  [Phase 3 Complete]")
    print("    Partial-hash groups with dups: {:,}".format(len(candidates)))
    print("    Files needing full hash:       {:,}".format(n_cand))
    print("    Errors:                        {:,}".format(errors))

    return candidates


# ═══════════════════════════════════════════════════════════════════
# PHASE 4: Full SHA-256 hash
# ═══════════════════════════════════════════════════════════════════

def phase4_full_hash(partial_groups):
    print("\n" + "=" * 74)
    print("  PHASE 4: Full SHA-256 hash confirmation")
    print("=" * 74 + "\n")

    hash_map = defaultdict(list)
    total = sum(len(v) for v in partial_groups.values())
    done = 0
    errors = 0
    bytes_hashed = 0

    for key, files in sorted(partial_groups.items(), key=lambda x: -x[1][0]["size"]):
        for f in files:
            done += 1
            if done % 100 == 0:
                print("  [Full Hash] {}/{} ({} hashed)...".format(done, total, human_size(bytes_hashed)))
            fh = full_hash(f["path"])
            if fh:
                hkey = "{}_{}".format(fh, f["size"])
                hash_map[hkey].append(f)
                bytes_hashed += f["size"]
            else:
                errors += 1

    duplicates = {k: v for k, v in hash_map.items() if len(v) >= 2}
    total_dup_files = sum(len(v) for v in duplicates.values())
    total_wasted = sum(v[0]["size"] * (len(v) - 1) for v in duplicates.values())

    print("\n  [Phase 4 Complete]")
    print("    Total bytes hashed:     {}".format(human_size(bytes_hashed)))
    print("    Confirmed dup groups:   {:,}".format(len(duplicates)))
    print("    Confirmed dup files:    {:,}".format(total_dup_files))
    print("    Total wasted space:     {}".format(human_size(total_wasted)))
    print("    Errors:                 {:,}".format(errors))

    return duplicates


# ═══════════════════════════════════════════════════════════════════
# PHASE 5: Category & extension analytics
# ═══════════════════════════════════════════════════════════════════

def phase5_analytics(all_files, duplicates):
    print("\n" + "=" * 74)
    print("  PHASE 5: Category & extension analytics")
    print("=" * 74 + "\n")

    # Overall category breakdown
    cat_stats = defaultdict(lambda: {"count": 0, "size": 0})
    ext_stats = defaultdict(lambda: {"count": 0, "size": 0})

    for f in all_files:
        cat = f["category"]
        cat_stats[cat]["count"] += 1
        cat_stats[cat]["size"] += f["size"]
        ext = f["ext"] if f["ext"] else "(none)"
        ext_stats[ext]["count"] += 1
        ext_stats[ext]["size"] += f["size"]

    # Duplicate category breakdown
    dup_cat_stats = defaultdict(lambda: {"groups": 0, "files": 0, "wasted": 0})
    dup_ext_stats = defaultdict(lambda: {"groups": 0, "files": 0, "wasted": 0})

    for key, files in duplicates.items():
        cat = files[0]["category"]
        ext = files[0]["ext"] if files[0]["ext"] else "(none)"
        wasted = files[0]["size"] * (len(files) - 1)

        dup_cat_stats[cat]["groups"] += 1
        dup_cat_stats[cat]["files"] += len(files)
        dup_cat_stats[cat]["wasted"] += wasted

        dup_ext_stats[ext]["groups"] += 1
        dup_ext_stats[ext]["files"] += len(files)
        dup_ext_stats[ext]["wasted"] += wasted

    # Convert to serializable dicts
    cat_data = {}
    for cat in sorted(cat_stats.keys()):
        cat_data[cat] = {
            "total_files": cat_stats[cat]["count"],
            "total_size": cat_stats[cat]["size"],
            "total_size_human": human_size(cat_stats[cat]["size"]),
            "dup_groups": dup_cat_stats[cat]["groups"],
            "dup_files": dup_cat_stats[cat]["files"],
            "wasted": dup_cat_stats[cat]["wasted"],
            "wasted_human": human_size(dup_cat_stats[cat]["wasted"]),
        }

    # Top 30 extensions by wasted space
    top_exts = sorted(dup_ext_stats.items(), key=lambda x: -x[1]["wasted"])[:30]
    ext_data = {}
    for ext, stats in top_exts:
        ext_data[ext] = {
            "total_files": ext_stats[ext]["count"],
            "total_size": ext_stats[ext]["size"],
            "total_size_human": human_size(ext_stats[ext]["size"]),
            "dup_groups": stats["groups"],
            "dup_files": stats["files"],
            "wasted": stats["wasted"],
            "wasted_human": human_size(stats["wasted"]),
        }

    for cat, data in sorted(cat_data.items(), key=lambda x: -x[1]["wasted"]):
        if data["wasted"] > 0:
            print("  {:<14} {:>8} files | {:>10} total | {:>10} wasted in {} dup groups".format(
                cat, data["total_files"], data["total_size_human"], data["wasted_human"], data["dup_groups"]))

    return cat_data, ext_data


# ═══════════════════════════════════════════════════════════════════
# PHASE 6: Folder-level duplication analysis
# ═══════════════════════════════════════════════════════════════════

def phase6_folder_analysis(duplicates):
    print("\n" + "=" * 74)
    print("  PHASE 6: Folder-level duplication hotspots")
    print("=" * 74 + "\n")

    # Which folders have the most duplicates?
    folder_waste = defaultdict(lambda: {"dup_files": 0, "wasted": 0, "groups": set()})

    for key, files in duplicates.items():
        wasted_per_copy = files[0]["size"]
        dirs_in_group = set()
        for f in files:
            dirs_in_group.add(f["dir"])

        for f in files:
            folder_waste[f["dir"]]["dup_files"] += 1
            folder_waste[f["dir"]]["groups"].add(key)

        # Attribute wasted space to directories containing the "extra" copies
        files_sorted = sorted(files, key=lambda x: x["mtime"])
        for f in files_sorted[1:]:  # skip the oldest (original)
            folder_waste[f["dir"]]["wasted"] += wasted_per_copy

    # Find folder pairs that share many duplicates
    folder_pairs = defaultdict(lambda: {"shared_groups": 0, "shared_wasted": 0})
    for key, files in duplicates.items():
        dirs = list(set(f["dir"] for f in files))
        wasted_per = files[0]["size"]
        for i in range(len(dirs)):
            for j in range(i + 1, len(dirs)):
                pair = tuple(sorted([dirs[i], dirs[j]]))
                folder_pairs[pair]["shared_groups"] += 1
                folder_pairs[pair]["shared_wasted"] += wasted_per

    # Top folders by waste
    top_folders = sorted(folder_waste.items(), key=lambda x: -x[1]["wasted"])[:50]
    folder_data = []
    for fpath, stats in top_folders:
        folder_data.append({
            "path": fpath,
            "dup_files": stats["dup_files"],
            "wasted": stats["wasted"],
            "wasted_human": human_size(stats["wasted"]),
            "dup_groups": len(stats["groups"]),
        })

    # Top folder pairs
    top_pairs = sorted(folder_pairs.items(), key=lambda x: -x[1]["shared_wasted"])[:30]
    pair_data = []
    for (d1, d2), stats in top_pairs:
        pair_data.append({
            "folder_a": d1,
            "folder_b": d2,
            "shared_groups": stats["shared_groups"],
            "shared_wasted": stats["shared_wasted"],
            "shared_wasted_human": human_size(stats["shared_wasted"]),
        })

    for fd in folder_data[:10]:
        print("  {:>10} wasted | {:>4} dups | {}".format(fd["wasted_human"], fd["dup_files"], fd["path"]))

    if pair_data:
        print("\n  Top folder pairs sharing duplicates:")
        for pd in pair_data[:5]:
            print("    {:>10} shared | {} groups".format(pd["shared_wasted_human"], pd["shared_groups"]))
            print("      A: {}".format(pd["folder_a"]))
            print("      B: {}".format(pd["folder_b"]))

    return folder_data, pair_data


# ═══════════════════════════════════════════════════════════════════
# PHASE 7: Near-duplicate filename detection
# ═══════════════════════════════════════════════════════════════════

def phase7_near_duplicates(all_files):
    print("\n" + "=" * 74)
    print("  PHASE 7: Near-duplicate filename detection")
    print("=" * 74 + "\n")

    # Group files by extension + similar size (within 10%)
    size_ext_groups = defaultdict(list)
    for f in all_files:
        if f["size"] >= 10240:  # Only files >= 10KB
            bucket = f["size"] // (f["size"] // 10 + 1) if f["size"] > 0 else 0
            key = (f["ext"], bucket)
            size_ext_groups[key].append(f)

    near_dups = []
    checked = 0
    limit = 50  # Max near-dup groups to report

    for key, files in size_ext_groups.items():
        if len(files) < 2 or len(files) > 100:
            continue

        for i in range(len(files)):
            if len(near_dups) >= limit:
                break
            name_a = normalize_filename(os.path.splitext(files[i]["name"])[0])
            for j in range(i + 1, len(files)):
                name_b = normalize_filename(os.path.splitext(files[j]["name"])[0])
                if name_a == name_b and files[i]["path"] != files[j]["path"]:
                    # Same normalized name but different actual file — check if already exact dup
                    if files[i]["size"] != files[j]["size"]:
                        similarity = SequenceMatcher(None, name_a, name_b).ratio()
                        near_dups.append({
                            "file_a": files[i]["path"],
                            "file_b": files[j]["path"],
                            "name_a": files[i]["name"],
                            "name_b": files[j]["name"],
                            "size_a": files[i]["size"],
                            "size_b": files[j]["size"],
                            "size_a_human": human_size(files[i]["size"]),
                            "size_b_human": human_size(files[j]["size"]),
                            "similarity": round(similarity, 3),
                        })
            checked += 1

        if len(near_dups) >= limit:
            break

    # Also find files with typical "copy" patterns
    copy_pattern = re.compile(
        r'(?:.*\s*[\(\[]\d+[\)\]].*|.*\s*-\s*Copy.*|Copy\s+of\s+.*)',
        re.IGNORECASE
    )
    copy_files = []
    for f in all_files:
        if copy_pattern.match(f["name"]) and f["size"] >= 1024:
            copy_files.append({
                "path": f["path"],
                "name": f["name"],
                "size": f["size"],
                "size_human": human_size(f["size"]),
            })
    copy_files.sort(key=lambda x: -x["size"])
    copy_files = copy_files[:100]

    print("  Near-duplicate name pairs found: {:,}".format(len(near_dups)))
    print("  Files with 'copy' patterns:      {:,}".format(len(copy_files)))

    return near_dups, copy_files


# ═══════════════════════════════════════════════════════════════════
# PHASE 8: Empty folders & tiny files
# ═══════════════════════════════════════════════════════════════════

def phase8_cleanup_targets(all_files, all_dirs):
    print("\n" + "=" * 74)
    print("  PHASE 8: Empty folders & tiny file analysis")
    print("=" * 74 + "\n")

    # Find empty directories
    dirs_with_files = set(f["dir"] for f in all_files)
    empty_dirs = []
    for d in all_dirs:
        if d not in dirs_with_files:
            # Check if it has subdirectories
            try:
                contents = os.listdir(d)
                if not contents:
                    empty_dirs.append(d)
            except (PermissionError, OSError):
                pass

    # Tiny files analysis
    tiny_files = [f for f in all_files if f["size"] <= TINY_FILE_THRESHOLD and f["size"] > 0]
    tiny_total_size = sum(f["size"] for f in tiny_files)

    # Zero-byte files
    zero_files = [{"path": f["path"], "name": f["name"]} for f in all_files if f["size"] == 0]

    # Large files (top 50)
    large_files = sorted(all_files, key=lambda x: -x["size"])[:50]
    large_data = [{
        "path": f["path"],
        "name": f["name"],
        "size": f["size"],
        "size_human": human_size(f["size"]),
        "category": f["category"],
        "modified": datetime.fromtimestamp(f["mtime"]).strftime("%Y-%m-%d"),
    } for f in large_files]

    print("  Empty directories:  {:,}".format(len(empty_dirs)))
    print("  Zero-byte files:    {:,}".format(len(zero_files)))
    print("  Tiny files (<=1KB): {:,} ({})".format(len(tiny_files), human_size(tiny_total_size)))
    print("  Largest file:       {} ({})".format(
        large_data[0]["size_human"] if large_data else "N/A",
        large_data[0]["name"] if large_data else "N/A"))

    return empty_dirs, zero_files[:200], len(tiny_files), tiny_total_size, large_data


# ═══════════════════════════════════════════════════════════════════
# REPORT BUILDER
# ═══════════════════════════════════════════════════════════════════

def build_duplicate_groups(duplicates):
    groups = []
    total_wasted = 0

    sorted_keys = sorted(duplicates.keys(), key=lambda k: -duplicates[k][0]["size"] * (len(duplicates[k]) - 1))

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
            "category": files[0]["category"],
            "extension": files[0]["ext"],
            "files": [
                {
                    "path": f["path"],
                    "name": f["name"],
                    "dir": f["dir"],
                    "modified": datetime.fromtimestamp(f["mtime"]).strftime("%Y-%m-%d %H:%M:%S"),
                    "is_oldest": (i == 0),
                }
                for i, f in enumerate(files_sorted)
            ],
        }
        groups.append(group)

    return groups, total_wasted


def build_full_report(all_files, all_dirs, error_paths, total_size, duplicates,
                      cat_data, ext_data, folder_data, pair_data,
                      near_dups, copy_files, empty_dirs, zero_files,
                      tiny_count, tiny_size, large_files, scan_time):

    groups, total_wasted = build_duplicate_groups(duplicates)

    # Folder tree stats (top-level folder breakdown)
    toplevel_stats = defaultdict(lambda: {"files": 0, "size": 0})
    for f in all_files:
        rel = os.path.relpath(f["path"], ROOT_PATH)
        top = rel.split(os.sep)[0]
        toplevel_stats[top]["files"] += 1
        toplevel_stats[top]["size"] += f["size"]

    toplevel_data = []
    for name in sorted(toplevel_stats.keys(), key=lambda x: -toplevel_stats[x]["size"]):
        toplevel_data.append({
            "name": name,
            "files": toplevel_stats[name]["files"],
            "size": toplevel_stats[name]["size"],
            "size_human": human_size(toplevel_stats[name]["size"]),
        })

    report = {
        "meta": {
            "scan_root": ROOT_PATH,
            "scan_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "scan_duration_seconds": round(scan_time, 2),
            "scanner_version": "2.0",
        },
        "overview": {
            "total_files": len(all_files),
            "total_directories": len(all_dirs),
            "total_size": total_size,
            "total_size_human": human_size(total_size),
            "total_duplicate_groups": len(groups),
            "total_duplicate_files": sum(g["count"] for g in groups),
            "total_wasted_bytes": total_wasted,
            "total_wasted_human": human_size(total_wasted),
            "wasted_percentage": round(total_wasted / total_size * 100, 2) if total_size > 0 else 0,
            "empty_directories": len(empty_dirs),
            "zero_byte_files": len(zero_files),
            "tiny_files_count": tiny_count,
            "tiny_files_size": tiny_size,
            "tiny_files_size_human": human_size(tiny_size),
            "error_count": len(error_paths),
        },
        "toplevel_folders": toplevel_data[:50],
        "category_breakdown": cat_data,
        "extension_breakdown": ext_data,
        "duplicate_groups": groups,
        "folder_hotspots": folder_data,
        "folder_pairs": pair_data,
        "near_duplicates": near_dups,
        "copy_pattern_files": copy_files,
        "empty_directories": empty_dirs[:200],
        "zero_byte_files": zero_files,
        "largest_files": large_files,
        "errors": error_paths[:200],
    }

    return report


# ═══════════════════════════════════════════════════════════════════
# TEXT SUMMARY
# ═══════════════════════════════════════════════════════════════════

def write_text_summary(report):
    L = []
    o = report["overview"]
    m = report["meta"]

    L.append("=" * 80)
    L.append("  DEEP DUPLICATE SCAN REPORT v2.0")
    L.append("  Root:     {}".format(m["scan_root"]))
    L.append("  Date:     {}".format(m["scan_date"]))
    L.append("  Duration: {}s".format(m["scan_duration_seconds"]))
    L.append("=" * 80)
    L.append("")
    L.append("  +-----------------------------------------------------------+")
    L.append("  | OVERVIEW                                               |")
    L.append("  +-----------------------------------------------------------+")
    L.append("  | Total files:          {:>10,}                        |".format(o["total_files"]))
    L.append("  | Total directories:    {:>10,}                        |".format(o["total_directories"]))
    L.append("  | Total size:           {:>14}                    |".format(o["total_size_human"]))
    L.append("  | Duplicate groups:     {:>10,}                        |".format(o["total_duplicate_groups"]))
    L.append("  | Duplicate files:      {:>10,}                        |".format(o["total_duplicate_files"]))
    L.append("  | WASTED SPACE:         {:>14}                    |".format(o["total_wasted_human"]))
    L.append("  | Waste percentage:     {:>9.2f}%                        |".format(o["wasted_percentage"]))
    L.append("  | Empty directories:    {:>10,}                        |".format(o["empty_directories"]))
    L.append("  | Zero-byte files:      {:>10,}                        |".format(o["zero_byte_files"]))
    L.append("  | Errors:               {:>10,}                        |".format(o["error_count"]))
    L.append("  +-----------------------------------------------------------+")
    L.append("")

    # Category breakdown
    L.append("  CATEGORY BREAKDOWN (by wasted space):")
    L.append("  " + "-" * 76)
    for cat, data in sorted(report["category_breakdown"].items(), key=lambda x: -x[1]["wasted"]):
        if data["wasted"] > 0:
            L.append("    {:<14} {:>6} files total | {:>10} size | {:>10} WASTED ({} groups)".format(
                cat, data["total_files"], data["total_size_human"], data["wasted_human"], data["dup_groups"]))
    L.append("")

    # Top 30 duplicate groups
    L.append("  TOP 30 DUPLICATE GROUPS BY WASTED SPACE:")
    L.append("  " + "-" * 76)
    for i, g in enumerate(report["duplicate_groups"][:30], 1):
        L.append("")
        L.append("  #{}: {} wasted | {} copies of {} [{}]".format(
            i, g["wasted_human"], g["count"], g["file_size_human"], g["category"]))
        L.append("  Hash: {}...".format(g["hash"][:20]))
        for f in g["files"]:
            marker = " [KEEP/OLDEST]" if f["is_oldest"] else ""
            L.append("    -> {}{}".format(f["path"], marker))
            L.append("       Modified: {}".format(f["modified"]))
    L.append("")

    # Folder hotspots
    L.append("  TOP 20 FOLDER HOTSPOTS:")
    L.append("  " + "-" * 76)
    for fd in report["folder_hotspots"][:20]:
        L.append("    {:>10} wasted | {:>4} dup files | {}".format(
            fd["wasted_human"], fd["dup_files"], fd["path"]))
    L.append("")

    # Folder pairs
    if report["folder_pairs"]:
        L.append("  TOP 10 FOLDER PAIRS SHARING DUPLICATES:")
        L.append("  " + "-" * 76)
        for pd in report["folder_pairs"][:10]:
            L.append("    {:>10} shared across {} groups:".format(pd["shared_wasted_human"], pd["shared_groups"]))
            L.append("      A: {}".format(pd["folder_a"]))
            L.append("      B: {}".format(pd["folder_b"]))
        L.append("")

    # Largest files
    L.append("  TOP 20 LARGEST FILES:")
    L.append("  " + "-" * 76)
    for lf in report["largest_files"][:20]:
        L.append("    {:>10} | {} | {}".format(lf["size_human"], lf["category"], lf["path"]))
    L.append("")

    # Copy pattern files
    if report["copy_pattern_files"]:
        L.append("  FILES WITH 'COPY' NAMING PATTERNS (top 30):")
        L.append("  " + "-" * 76)
        for cf in report["copy_pattern_files"][:30]:
            L.append("    {:>10} | {}".format(cf["size_human"], cf["path"]))
        L.append("")

    L.append("=" * 80)
    L.append("  END OF REPORT")
    L.append("=" * 80)

    return "\n".join(L)


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    print("\n" + "=" * 74)
    print("  DEEP DUPLICATE SCANNER v2.0")
    print("  Target: {}".format(ROOT_PATH))
    print("  Started: {}".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    print("=" * 74)

    os.makedirs(REPORT_DIR, exist_ok=True)
    t0 = time.time()

    # Phase 1: Index everything
    all_files, all_dirs, error_paths, total_size = phase1_index(ROOT_PATH)

    # Phase 2: Size grouping
    size_groups = phase2_size_group(all_files)

    # Phase 3: Partial hash
    partial_groups = phase3_partial_hash(size_groups)

    # Phase 4: Full hash
    duplicates = phase4_full_hash(partial_groups)

    # Phase 5: Analytics
    cat_data, ext_data = phase5_analytics(all_files, duplicates)

    # Phase 6: Folder analysis
    folder_data, pair_data = phase6_folder_analysis(duplicates)

    # Phase 7: Near-duplicates
    near_dups, copy_files = phase7_near_duplicates(all_files)

    # Phase 8: Cleanup targets
    empty_dirs, zero_files, tiny_count, tiny_size, large_files = phase8_cleanup_targets(all_files, all_dirs)

    scan_time = time.time() - t0

    # Build report
    report = build_full_report(
        all_files, all_dirs, error_paths, total_size, duplicates,
        cat_data, ext_data, folder_data, pair_data,
        near_dups, copy_files, empty_dirs, zero_files,
        tiny_count, tiny_size, large_files, scan_time
    )

    # Save JSON
    with open(JSON_REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print("\n  JSON report: {}".format(JSON_REPORT))

    # Save text
    text = write_text_summary(report)
    with open(TEXT_REPORT, "w", encoding="utf-8") as f:
        f.write(text)
    print("  Text report: {}".format(TEXT_REPORT))

    # Final summary
    o = report["overview"]
    print("\n" + "=" * 74)
    print("  SCAN COMPLETE")
    print("=" * 74)
    print("  Files scanned:        {:,}".format(o["total_files"]))
    print("  Directories:          {:,}".format(o["total_directories"]))
    print("  Total size:           {}".format(o["total_size_human"]))
    print("  Duplicate groups:     {:,}".format(o["total_duplicate_groups"]))
    print("  Duplicate files:      {:,}".format(o["total_duplicate_files"]))
    print("  WASTED SPACE:         {} ({:.2f}%)".format(o["total_wasted_human"], o["wasted_percentage"]))
    print("  Empty directories:    {:,}".format(o["empty_directories"]))
    print("  Scan time:            {:.1f}s".format(scan_time))
    print("=" * 74)
    print("\n  Open the dashboard:   {}".format(
        os.path.join(REPORT_DIR, "dashboard.html")))
    print("")


if __name__ == "__main__":
    main()
