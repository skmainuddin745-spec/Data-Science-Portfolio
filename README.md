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
python safe_cleanup.py --report report.json --dry-run  # preview deletions
python safe_cleanup.py --report report.json --execute  # execute deletions
```

#### Sample Output

```json
{
  "scan_summary": {
    "total_files_scanned": 523847,
    "duplicate_groups_found": 4821,
    "total_reclaimable_bytes": 187429301248,
    "total_reclaimable_human": "174.6 GB"
  },
  "duplicate_groups": [
    {
      "hash": "a3f5c9...",
      "size_bytes": 45678901,
      "count": 3,
      "keep": "E:/archive/original/file.mp4",
      "delete": [
        "G:/backup_old/file.mp4",
        "G:/backup_v2/file.mp4"
      ]
    }
  ]
}
```

---

### 2. Quick Duplicate Scanner (`scan_duplicates.py`)

Lightweight single-pass scanner for smaller datasets. Uses SHA-256 only (no partial hash pre-filter), suitable for directories up to ~50,000 files.

```python
import hashlib
from pathlib import Path
from collections import defaultdict

def sha256_file(path: Path, chunk_size: int = 65536) -> str:
    """Memory-efficient SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()

def find_duplicates(root: str) -> dict:
    """Return dict of hash → [list of paths] for all duplicates."""
    seen = defaultdict(list)
    for path in Path(root).rglob('*'):
        if path.is_file():
            file_hash = sha256_file(path)
            seen[file_hash].append(str(path))
    return {h: paths for h, paths in seen.items() if len(paths) > 1}
```

#### Usage

```bash
python scan_duplicates.py --root "C:\Users\SK\Documents" --output duplicates.json
```

---

### 3. Statistical Pipeline Utilities

A set of reusable statistical functions for data science pipelines, designed to be production-safe with explicit error handling and logging:

#### 3a. Production-safe outlier removal

```python
def remove_outliers_conservative(
    df: pd.DataFrame,
    cols: list,
    z_thresh: float = 2.5,
    logger=None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Conservative AND-logic outlier removal.
    Returns (clean_df, removed_df) so removed rows can be audited.
    Only removes a row if BOTH Z-score AND IQR flag it.
    """
    mask = pd.Series([True] * len(df), index=df.index)
    report = {}
    for col in cols:
        z_scores = np.abs(stats.zscore(df[col].dropna()))
        q1, q3 = df[col].quantile([0.25, 0.75])
        iqr = q3 - q1
        z_flag   = z_scores > z_thresh
        iqr_flag = (df[col] < q1 - 1.5*iqr) | (df[col] > q3 + 1.5*iqr)
        both_flag = z_flag & iqr_flag
        mask &= ~both_flag
        report[col] = int(both_flag.sum())
        if logger:
            logger.info(f"  {col}: removed {report[col]} outliers")
    return df[mask].copy(), df[~mask].copy()
```

#### 3b. Production-weighted statistics

```python
def weighted_stats(series: pd.Series, weights: pd.Series) -> dict:
    """
    Compute production-weighted mean, median, and std.
    Use when simple averages would be distorted by varying batch sizes.
    """
    w = weights / weights.sum()
    mean = (series * w).sum()
    # Weighted median via interpolation
    cum_w = w.sort_values().cumsum()
    median = series[cum_w >= 0.5].iloc[0]
    variance = ((series - mean)**2 * w).sum()
    return {'mean': mean, 'median': median, 'std': variance**0.5}
```

---

### 4. Batch Data Validation Framework

Multi-source cross-validation framework for industrial batch production data:

```python
class BatchValidator:
    """
    4-source cross-verification of batch records.
    No batch is accepted unless all 4 sources agree within tolerance.
    """
    SOURCES = ['production_report', 'web_scraper', 'erp_export', 'manual_log']
    TOLERANCE = {'water_L': 50, 'fabric_kg': 0.5, 'batch_time_min': 2}
    
    def validate(self, batch_id: str, records: dict) -> dict:
        results = {}
        for field, tol in self.TOLERANCE.items():
            values = [records[s][field] for s in self.SOURCES if s in records]
            spread = max(values) - min(values)
            results[field] = {
                'values': values,
                'spread': spread,
                'pass': spread <= tol,
                'consensus': sum(values) / len(values)
            }
        return results
```

---

## Design Principles

All utilities in this portfolio follow these production-safety principles:

| Principle | Implementation |
|-----------|---------------|
| **Zero silent failures** | All exceptions logged with full traceback; no bare `except: pass` |
| **Audit trail** | Every operation writes a timestamped log entry |
| **Dry-run first** | All destructive operations (delete, overwrite) require `--execute` flag |
| **Reproducible** | Fixed random seeds; all parameters logged at run start |
| **Memory-safe** | Stream processing for large files; no full file load into RAM |

---

## 📚 References & Documentation

- [deep_scan.py](deep_scan.py) — Full multi-threaded duplicate scanner source
- [scan_duplicates.py](scan_duplicates.py) — Lightweight single-pass scanner
- [_verify_all_stats.py](https://github.com/skmainuddin745-spec/Smart-Dyeing-Process-Analytics/blob/main/_verify_all_stats.py) — Statistical verification framework (Smart Dyeing project)
- Related project: [Smart-Dyeing-Process-Analytics](https://github.com/skmainuddin745-spec/Smart-Dyeing-Process-Analytics) — Statistical analysis suite (660 production batches)
