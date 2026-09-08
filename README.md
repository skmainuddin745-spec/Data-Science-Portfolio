# Data Science Portfolio — Analysis & Utility Scripts

> **A collection of production-grade data science utilities: large-scale duplicate file detection, statistical analysis tools, and data pipeline scripts.**

---

## Projects in this Portfolio

---

### 1. Intelligent Duplicate File Scanner (`deep_scan.py`)

**Purpose:** Recursively scan multi-terabyte directory trees, detect exact and near-duplicate files using multi-strategy hashing, and generate actionable cleanup reports.

#### Algorithm

```
Stage 1: Fast pre-filter
  → Group files by exact size
  → Discard singleton size groups (cannot be duplicates)

Stage 2: Partial hash (first 64 KB)
  → xxHash of first 64 KB of each candidate
  → Further group by (size, partial_hash)

Stage 3: Full SHA-256 fingerprint
  → Only computed for files that match in Stage 2
  → True duplicates: identical full hash

Stage 4: Report generation
  → JSON report with all duplicate groups
  → Estimated reclaimable space per group
  → Safe-to-delete recommendations (keeps oldest/most-accessed copy)
```

#### Performance

- Processes **500,000+ files** without loading any file content into RAM
- Multi-threaded I/O using `concurrent.futures.ThreadPoolExecutor`
- Progress reported every 1000 files via `tqdm`

#### Usage

```bash
python deep_scan.py --root E:\ G:\ --output report.json --workers 8
python safe_cleanup.py --report report.json --dry-run  # preview
python safe_cleanup.py --report report.json --execute  # delete
```

---

### 2. Quick Duplicate Scanner (`scan_duplicates.py`)

Lightweight single-pass scanner for smaller datasets. Uses SHA-256 only (no multi-stage pre-filter). Produces a concise HTML dashboard (`dashboard.html`) with sortable duplicate groups.

```bash
python scan_duplicates.py --path F:\ --min-size 10MB
```

---

### 3. Safe Cleanup Utility (`safe_cleanup.py`)

Reads a `deep_scan_report.json` and performs **verified** deletion:
- Presents human-readable summary before any deletion
- Keeps the **original** (oldest modification time) in each duplicate group
- Moves to Recycle Bin via `send2trash` (recoverable) or hard-deletes on confirmation
- Writes deletion audit log

---

## File Index

| File | Lines | Description |
|------|-------|-------------|
| `deep_scan.py` | ~870 | Multi-strategy duplicate detector |
| `scan_duplicates.py` | ~225 | Quick SHA-256 scanner |
| `safe_cleanup.py` | ~115 | Verified cleanup with audit log |

---

## Technology Stack

- **Python 3.10+** — `os`, `hashlib`, `json`, `concurrent.futures`
- **xxHash** — ultra-fast partial hashing (Stage 2 pre-filter)
- **tqdm** — progress bars for long-running scans
- **send2trash** — safe deletion (Recycle Bin)

---

## Sample Output

```json
{
  "scan_summary": {
    "total_files": 487293,
    "total_size_gb": 842.7,
    "duplicate_groups": 1247,
    "reclaimable_gb": 124.3,
    "scan_duration_s": 387.2
  },
  "duplicates": [
    {
      "hash": "a3f5c...",
      "size_bytes": 15728640,
      "count": 3,
      "files": [
        "E:\\backup\\report_final.pdf",
        "G:\\archive\\report_final.pdf",
        "F:\\Downloads\\report_final.pdf"
      ],
      "keep": "E:\\backup\\report_final.pdf",
      "reclaimable_bytes": 31457280
    }
  ]
}
```

---

*Data Science · Python · File Systems · Automation · Algorithms*
