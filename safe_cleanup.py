import json
import os
import shutil
from datetime import datetime

REPORT_PATH = r"G:\__duplicate_scanner\deep_scan_report.json"
TRASH_DIR = r"G:\__duplicate_trash"
LOG_FILE = r"G:\__duplicate_scanner\cleanup_log.txt"
SCANNER_DIR = r"G:\__duplicate_scanner"

def log_msg(msg, f_log=None):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('ascii', 'replace').decode('ascii'))
    if f_log:
        f_log.write("[{}] {}\n".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), msg))

def extend_path(p):
    if p.startswith("\\\\?\\"):
        return p
    return "\\\\?\\" + os.path.abspath(p)

def get_trash_path(original_path):
    drive, tail = os.path.splitdrive(original_path)
    drive_name = drive.replace(":", "_drive")
    tail = tail.lstrip("\\/")
    return os.path.join(TRASH_DIR, drive_name, tail)

def main():
    if not os.path.exists(REPORT_PATH):
        print("Error: Report not found at {}".format(REPORT_PATH))
        return

    print("Loading report...")
    with open(REPORT_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    groups = data.get("duplicate_groups", [])
    if not groups:
        print("No duplicate groups found to clean.")
        return

    if not os.path.exists(TRASH_DIR):
        os.makedirs(TRASH_DIR)
    
    total_moved = 0
    total_bytes_moved = 0
    errors = 0

    with open(LOG_FILE, 'w', encoding='utf-8') as log:
        log_msg("=== DUPLICATE CLEANUP LOG ===", log)
        log_msg("Starting safe move of duplicate files to trash...\n", log)

        for i, group in enumerate(groups):
            files = group["files"]
            if len(files) < 2:
                continue
            
            # Sort to find the best master file to KEEP:
            # 1. Shortest path length (usually indicates the most 'original' root location)
            # 2. Oldest modification date
            def sort_key(f):
                return (len(f["path"]), f["modified"])
            
            sorted_files = sorted(files, key=sort_key)
            master_file = sorted_files[0]
            duplicates = sorted_files[1:]

            log_msg("Group #{} - Keeping master: {}".format(i+1, master_file['path']), log)

            for dup in duplicates:
                src_path = dup["path"]
                if not os.path.exists(src_path):
                    log_msg("  [SKIPPED] File no longer exists: {}".format(src_path), log)
                    continue

                if src_path.startswith(SCANNER_DIR) or src_path.startswith(TRASH_DIR):
                    log_msg("  [SKIPPED] Protected path: {}".format(src_path), log)
                    continue

                dst_path = get_trash_path(src_path)
                dst_dir = os.path.dirname(dst_path)
                
                ext_src = extend_path(src_path)
                ext_dst = extend_path(dst_path)
                ext_dst_dir = extend_path(dst_dir)

                if not os.path.exists(ext_dst_dir):
                    os.makedirs(ext_dst_dir)

                try:
                    os.rename(ext_src, ext_dst)
                    log_msg("  [MOVED] {} -> {}".format(src_path, dst_path), log)
                    total_moved += 1
                    total_bytes_moved += dup.get("size", 0) # Fallback if size missing
                    if "file_size" in dup:
                        total_bytes_moved += dup["file_size"]
                except Exception as e:
                    log_msg("  [ERROR] Failed to move {}: {}".format(src_path, e), log)
                    errors += 1

        log_msg("\n=== EMPTY DIRECTORY CLEANUP ===", log)
        empty_deleted = 0
        
        for dirpath, dirnames, filenames in os.walk("G:\\", topdown=False):
            if dirpath.startswith(SCANNER_DIR) or dirpath.startswith(TRASH_DIR):
                continue
            
            try:
                ext_dir = extend_path(dirpath)
                if not os.listdir(ext_dir):
                    os.rmdir(ext_dir)
                    log_msg("  [DELETED EMPTY DIR] {}".format(dirpath), log)
                    empty_deleted += 1
            except Exception as e:
                pass 

        mb_saved = total_bytes_moved / (1024 * 1024)
        gb_saved = mb_saved / 1024
        log_msg("\n=== CLEANUP COMPLETE ===", log)
        log_msg("Total files moved to trash: {:,}".format(total_moved), log)
        log_msg("Total space freed: {:.2f} GB ({:.2f} MB)".format(gb_saved, mb_saved), log)
        log_msg("Empty directories removed: {:,}".format(empty_deleted), log)
        log_msg("Errors encountered: {:,}".format(errors), log)

if __name__ == "__main__":
    main()
