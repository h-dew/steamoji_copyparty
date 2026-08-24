import os
import sys
import shutil
import logging
import time
import argparse
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

try:
    import tomllib  # stdlib in 3.11+
except ImportError:
    try:
        import tomli as tomllib  # fallback for older python
    except ImportError:
        tomllib = None

# default paths.toml template generated if missing
DEFAULT_CONFIG_TOML = """# Configuration file for drive and folder paths

[drives]
# Drives mounted under /mnt or /media
storage = "storage"
backup = "backup"

[folders]
# Folders located inside the storage drive root
apprenticeFolder = "apprentice_folders"
projectFilesFolder = "project_files"
miscFolder = "misc"

[backup]
# Subdirectory on backup drive where timestamped backups are stored
backup_dir = "backups"

# Directory or zip archive naming template
folder_name_format = "backup_%Y-%m-%d_%H-%M-%S"

# Number of weekly backups to keep
keep_backups = 8

# Number of monthly backups to keep (keeps first backup of each month)
keep_monthly_months = 6

# Minimum number of days between automated backups
backup_interval_days = 7

# Path to the log file
log_file = "/var/log/fileserver_backup.log"

# Lock file path to prevent overlapping runs
lock_file = "/var/run/fileserver_backup.lock"

[backup_options]
# Which folders from the [folders] section to include in the backup
active_folders = [
    "apprenticeFolder"
]

# Minimum free storage required on destination drive (in GB)
min_disk_space_gb = 150.0

# Compress backups into single zip archives (.zip)
zip_backup = true

# Use DEFLATE compression (true = smaller file; false = uncompressed ZIP_STORED)
zip_compression = true

# File patterns to exclude from backup
ignore_patterns = [
    "*.tmp",
    "~$*",
    ".DS_Store",
    "Thumbs.db",
    "*.lock",
    "*.hist"
]

# Stop backup job immediately on first copy error if true
strict_mode = false
"""


class BackupConfig:
    def __init__(self, config_path: str = "paths.toml"):
        cp = Path(config_path)
        if not cp.exists() and not cp.is_absolute():
            script_dir_cp = Path(__file__).resolve().parent / config_path
            if script_dir_cp.exists():
                cp = script_dir_cp

        self.config_path = cp
        self.raw_config: Dict[str, Any] = {}
        self.storage_drive: Path = Path("/mnt/storage")
        self.backup_drive: Path = Path("/mnt/backup")
        self.destination_root: Path = Path("/mnt/backup/backups")
        self.folder_name_format: str = "backup_%Y-%m-%d_%H-%M-%S"
        self.keep_backups: int = 8
        self.keep_monthly_months: int = 6
        self.backup_interval_days: int = 7
        self.log_file: Path = Path("/var/log/fileserver_backup.log")
        self.lock_file: Path = Path("/var/run/fileserver_backup.lock")
        self.sources: Dict[str, Path] = {}
        self.min_disk_space_gb: float = 150.0
        self.zip_backup: bool = True
        self.zip_compression: bool = True
        self.active_folders: List[str] = ["apprenticeFolder"]
        self.ignore_patterns: List[str] = []
        self.strict_mode: bool = False

        self.load()

    # resolve drive path across standard linux mount locations
    def _resolve_drive_path(self, drive_name_or_path: str) -> Path:
        p = Path(drive_name_or_path)
        if p.is_absolute() and p.exists():
            return p

        candidates = [
            p,
            Path("/mnt") / drive_name_or_path,
            Path("/media") / drive_name_or_path,
            Path("/") / drive_name_or_path,
        ]
        for candidate in candidates:
            if candidate.exists() and candidate.is_dir():
                return candidate.resolve()

        return Path("/mnt") / drive_name_or_path

    def load(self) -> None:
        if not self.config_path.exists():
            print(f"[WARN] Config file '{self.config_path}' not found, creating default paths.toml")
            self.create_sample_config()

        if tomllib is None:
            raise RuntimeError("No TOML parser available. Run Python 3.11+ or install 'tomli'.")

        with open(self.config_path, "rb") as f:
            self.raw_config = tomllib.load(f)

        drives_sec = self.raw_config.get("drives", {})
        storage_drive_raw = drives_sec.get("storage", "storage")
        backup_drive_raw = drives_sec.get("backup", "backup")

        self.storage_drive = self._resolve_drive_path(storage_drive_raw)
        self.backup_drive = self._resolve_drive_path(backup_drive_raw)

        backup_sec = self.raw_config.get("backup", {})
        backup_dir_name = backup_sec.get("backup_dir", "backups")
        self.destination_root = self.backup_drive / backup_dir_name
        self.folder_name_format = backup_sec.get("folder_name_format", "backup_%Y-%m-%d_%H-%M-%S")
        self.keep_backups = int(backup_sec.get("keep_backups", 8))
        self.keep_monthly_months = int(backup_sec.get("keep_monthly_months", 6))
        self.backup_interval_days = int(backup_sec.get("backup_interval_days", 7))
        self.log_file = Path(backup_sec.get("log_file", "/var/log/fileserver_backup.log"))
        self.lock_file = Path(backup_sec.get("lock_file", "/var/run/fileserver_backup.lock"))

        opts_sec = self.raw_config.get("backup_options") or self.raw_config.get("options", {})
        self.active_folders = opts_sec.get("active_folders", ["apprenticeFolder"])

        folders_sec = self.raw_config.get("folders", {})
        self.sources = {}
        for key, rel_path in folders_sec.items():
            if self.active_folders and key not in self.active_folders:
                continue
            self.sources[key] = self.storage_drive / rel_path

        self.min_disk_space_gb = float(opts_sec.get("min_disk_space_gb", 150.0))
        self.zip_backup = bool(opts_sec.get("zip_backup", True))
        self.zip_compression = bool(opts_sec.get("zip_compression", True))
        self.ignore_patterns = opts_sec.get("ignore_patterns", ["*.tmp", "~$*", ".DS_Store", "Thumbs.db", "*.hist"])
        self.strict_mode = bool(opts_sec.get("strict_mode", False))

    # create sample config if paths.toml missing
    def create_sample_config(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write(DEFAULT_CONFIG_TOML)
        print(f"[INFO] Created default paths configuration at '{self.config_path}'")


class FileServerBackup:
    def __init__(self, config_path: str = "paths.toml", dry_run: bool = False, force: bool = False):
        self.dry_run = dry_run
        self.force = force
        self.config = BackupConfig(config_path)
        self.logger = self._setup_logger()
        self.start_time = time.time()
        self.total_files_copied = 0
        self.total_bytes_copied = 0
        self.error_count = 0

    # configure console and logfile outputs with permission fallback
    def _setup_logger(self) -> logging.Logger:
        logger = logging.getLogger("FileserverBackup")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()

        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

        if not self.dry_run:
            target_log = self.config.log_file
            try:
                target_log.parent.mkdir(parents=True, exist_ok=True)
                fh = logging.FileHandler(target_log, encoding="utf-8")
                fh.setFormatter(formatter)
                logger.addHandler(fh)
            except Exception as e:
                fallback_log = Path(__file__).resolve().parent / "fileserver_backup.log"
                try:
                    fh = logging.FileHandler(fallback_log, encoding="utf-8")
                    fh.setFormatter(formatter)
                    logger.addHandler(fh)
                    logger.warning(f"Could not open '{target_log}' ({e}), using '{fallback_log}' instead.")
                except Exception:
                    logger.warning("Could not open log files, logging to console only.")

        return logger

    # acquire lock file to prevent overlapping jobs
    def _acquire_lock(self) -> bool:
        if self.dry_run:
            return True

        lock_path = self.config.lock_file
        try:
            if lock_path.exists():
                try:
                    pid = int(lock_path.read_text().strip())
                    os.kill(pid, 0)
                    self.logger.error(f"Backup already running with PID {pid}. Aborting.")
                    return False
                except ProcessLookupError:
                    self.logger.warning(f"Removing stale lock file from dead process at {lock_path}.")
                    lock_path.unlink(missing_ok=True)
                except PermissionError:
                    self.logger.error("Backup already running under another user PID. Aborting.")
                    return False
                except (ValueError, FileNotFoundError):
                    lock_path.unlink(missing_ok=True)

            lock_path.parent.mkdir(parents=True, exist_ok=True)
            lock_path.write_text(str(os.getpid()))
            return True
        except PermissionError:
            fallback_lock = Path("/tmp") / f"fileserver_backup_{os.getuid()}.lock"
            self.config.lock_file = fallback_lock
            try:
                fallback_lock.write_text(str(os.getpid()))
                return True
            except Exception as e:
                self.logger.error(f"Failed to acquire lock file at fallback path '{fallback_lock}': {e}")
                return False
        except Exception as e:
            self.logger.error(f"Failed to acquire lock file: {e}")
            return False

    # remove lock file on exit
    def _release_lock(self) -> None:
        if self.dry_run:
            return
        try:
            if self.config.lock_file.exists():
                pid = int(self.config.lock_file.read_text().strip())
                if pid == os.getpid():
                    self.config.lock_file.unlink(missing_ok=True)
        except Exception as e:
            self.logger.warning(f"Could not remove lock file: {e}")

    # parse timestamp from backup name or fallback to filesystem modification time
    def _get_backup_datetime(self, backup_path: Path) -> datetime:
        clean_name = backup_path.name.removesuffix(".zip")
        try:
            return datetime.strptime(clean_name, self.config.folder_name_format)
        except ValueError:
            return datetime.fromtimestamp(backup_path.stat().st_mtime)

    # check if minimum backup interval has elapsed
    def is_backup_due(self) -> Tuple[bool, str]:
        if self.force:
            return True, "Force flag set; skipping interval check."

        dest_root = self.config.destination_root
        if not dest_root.exists():
            return True, "No backup directory exists yet."

        prefix = self.config.folder_name_format.split("%")[0]
        existing_backups = [
            p for p in dest_root.iterdir()
            if (p.is_dir() or p.name.endswith(".zip")) and p.name.startswith(prefix)
        ]

        if not existing_backups:
            return True, "No previous backups found."

        latest_dt = max(self._get_backup_datetime(p) for p in existing_backups)
        next_due = latest_dt + timedelta(days=self.config.backup_interval_days)
        now = datetime.now()

        if now >= next_due:
            return True, f"Last backup was at {latest_dt.strftime('%Y-%m-%d %H:%M:%S')}. Interval met."
        else:
            remaining = next_due - now
            days_left = remaining.days
            hours_left = remaining.seconds // 3600
            return False, f"Last backup was at {latest_dt.strftime('%Y-%m-%d %H:%M:%S')}. Next backup due in {days_left}d {hours_left}h."

    # verify drives, destination path, disk space, and schedule before running
    def check_preflight(self) -> bool:
        self.logger.info("Checking paths and disk space...")

        if not self.config.storage_drive.exists():
            self.logger.error(f"Storage drive not found at '{self.config.storage_drive}'")
            return False

        if not self.config.backup_drive.exists():
            self.logger.error(f"Backup drive not found at '{self.config.backup_drive}'")
            return False

        try:
            if not self.dry_run:
                self.config.destination_root.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.logger.error(f"Cannot create backup destination directory '{self.config.destination_root}': {e}")
            return False

        due, reason = self.is_backup_due()
        self.logger.info(f"Backup schedule check: {reason}")
        if not due:
            self.logger.info("Backup skipped (not due yet). Use -f or force=True to override.")
            return False

        try:
            usage = shutil.disk_usage(self.config.backup_drive)
            free_gb = usage.free / (1024 ** 3)
            self.logger.info(f"Free disk space on backup drive: {free_gb:.2f} GB (Required: {self.config.min_disk_space_gb:.2f} GB)")
            if free_gb < self.config.min_disk_space_gb:
                self.logger.error(f"Insufficient disk space! {free_gb:.2f} GB free, but {self.config.min_disk_space_gb:.2f} GB required.")
                return False
        except Exception as e:
            self.logger.warning(f"Could not verify disk space: {e}")

        valid_sources = [p for p in self.config.sources.values() if p.exists()]
        if not valid_sources:
            self.logger.error("None of the configured source folders exist on storage drive!")
            return False

        return True

    def _copy_directory_tree(self, src: Path, dst: Path) -> None:
        ignore_spec = shutil.ignore_patterns(*self.config.ignore_patterns)

        for root, dirs, files in os.walk(src):
            rel_path = Path(root).relative_to(src)
            target_dir = dst / rel_path

            ignored_names = ignore_spec(root, dirs + files)
            dirs[:] = [d for d in dirs if d not in ignored_names]

            if not self.dry_run:
                target_dir.mkdir(parents=True, exist_ok=True)

            for file in files:
                if file in ignored_names:
                    continue

                src_file = Path(root) / file
                dst_file = target_dir / file

                try:
                    file_stat = src_file.stat(follow_symlinks=False)
                    file_size = file_stat.st_size

                    if not self.dry_run:
                        try:
                            shutil.copy2(src_file, dst_file)
                        except (PermissionError, OSError):
                            shutil.copy(src_file, dst_file)

                    self.total_files_copied += 1
                    self.total_bytes_copied += file_size
                except Exception as e:
                    self.error_count += 1
                    self.logger.error(f"Error copying '{src_file}': {e}")
                    if self.config.strict_mode:
                        raise RuntimeError(f"Strict mode enabled. Stopping on error: {e}")

    def _zip_directory_tree(self, src: Path, zip_file: Optional[zipfile.ZipFile], arc_prefix: str = "") -> None:
        ignore_spec = shutil.ignore_patterns(*self.config.ignore_patterns)

        for root, dirs, files in os.walk(src):
            rel_path = Path(root).relative_to(src)

            ignored_names = ignore_spec(root, dirs + files)
            dirs[:] = [d for d in dirs if d not in ignored_names]

            for file in files:
                if file in ignored_names:
                    continue

                src_file = Path(root) / file
                arc_name = Path(arc_prefix) / rel_path / file

                try:
                    file_stat = src_file.stat(follow_symlinks=False)
                    file_size = file_stat.st_size
                    if not self.dry_run and zip_file is not None:
                        zip_file.write(src_file, arcname=arc_name.as_posix())

                    self.total_files_copied += 1
                    self.total_bytes_copied += file_size
                except Exception as e:
                    self.error_count += 1
                    self.logger.error(f"Error zipping '{src_file}': {e}")
                    if self.config.strict_mode:
                        raise RuntimeError(f"Strict mode enabled. Stopping on error: {e}")

    def run_backup(self) -> bool:
        self.logger.info("=" * 60)
        self.logger.info(f"Starting fileserver backup {'(DRY RUN)' if self.dry_run else ''}")
        self.logger.info("=" * 60)

        if not self._acquire_lock():
            return False

        active_target: Optional[Path] = None

        try:
            if not self.check_preflight():
                self.logger.error("Preflight check failed or backup not due. Aborting backup.")
                return False

            timestamp = datetime.now().strftime(self.config.folder_name_format)

            if self.config.zip_backup:
                target_archive = self.config.destination_root / f"{timestamp}.zip"
                active_target = target_archive
                self.logger.info(f"Creating backup zip archive: {target_archive}")

                compression = zipfile.ZIP_DEFLATED if self.config.zip_compression else zipfile.ZIP_STORED

                if not self.dry_run:
                    with zipfile.ZipFile(target_archive, "w", compression=compression, allowZip64=True) as zf:
                        for name, src_path in self.config.sources.items():
                            if not src_path.exists():
                                self.logger.warning(f"Skipping missing source: '{name}' ({src_path})")
                                continue

                            arc_prefix = src_path.name
                            self.logger.info(f"Zipping [{name}] from {src_path} as '{arc_prefix}' ...")
                            self._zip_directory_tree(src_path, zf, arc_prefix=arc_prefix)
                else:
                    for name, src_path in self.config.sources.items():
                        if not src_path.exists():
                            self.logger.warning(f"Skipping missing source: '{name}' ({src_path})")
                            continue
                        arc_prefix = src_path.name
                        self.logger.info(f"Zipping [{name}] from {src_path} as '{arc_prefix}' ...")
                        self._zip_directory_tree(src_path, None, arc_prefix=arc_prefix)

            else:
                current_backup_dir = self.config.destination_root / timestamp
                active_target = current_backup_dir
                self.logger.info(f"Creating backup directory: {current_backup_dir}")
                if not self.dry_run:
                    current_backup_dir.mkdir(parents=True, exist_ok=True)

                for name, src_path in self.config.sources.items():
                    if not src_path.exists():
                        self.logger.warning(f"Skipping missing source: '{name}' ({src_path})")
                        continue

                    target_share_dir = current_backup_dir / name
                    self.logger.info(f"Backing up [{name}] from {src_path} ...")
                    self._copy_directory_tree(src_path, target_share_dir)

            self.prune_old_backups()

            duration = time.time() - self.start_time
            size_mb = self.total_bytes_copied / (1024 * 1024)
            size_gb = size_mb / 1024

            self.logger.info("-" * 60)
            self.logger.info("Backup complete!")
            self.logger.info(f"Files processed: {self.total_files_copied:,}")
            self.logger.info(f"Data processed:  {size_gb:.2f} GB ({size_mb:.2f} MB)")
            self.logger.info(f"Errors:          {self.error_count}")
            self.logger.info(f"Time taken:      {duration:.2f} seconds")
            self.logger.info("-" * 60)

            return True

        except Exception as e:
            self.logger.critical(f"Backup failed with error: {e}", exc_info=True)
            if active_target and active_target.exists():
                self.logger.info(f"Cleaning up incomplete backup: {active_target}")
                try:
                    if active_target.is_dir():
                        shutil.rmtree(active_target)
                    else:
                        active_target.unlink()
                except Exception as cleanup_err:
                    self.logger.error(f"Failed to clean up incomplete backup: {cleanup_err}")
            return False

        finally:
            self._release_lock()

    def prune_old_backups(self) -> None:
        dest_root = self.config.destination_root
        if not dest_root.exists():
            return

        prefix = self.config.folder_name_format.split("%")[0]
        backup_items: List[Tuple[Path, datetime]] = []

        for item in dest_root.iterdir():
            if (item.is_dir() or item.name.endswith(".zip")) and item.name.startswith(prefix):
                dt = self._get_backup_datetime(item)
                backup_items.append((item, dt))

        if not backup_items:
            return

        backup_items.sort(key=lambda x: x[1])
        protected_paths: set = set()

        keep_weekly = self.config.keep_backups
        if keep_weekly > 0:
            for path, _ in backup_items[-keep_weekly:]:
                protected_paths.add(path)

        keep_monthly = self.config.keep_monthly_months
        if keep_monthly > 0:
            monthly_groups: Dict[Tuple[int, int], List[Tuple[Path, datetime]]] = {}
            for path, dt in backup_items:
                month_key = (dt.year, dt.month)
                monthly_groups.setdefault(month_key, []).append((path, dt))

            sorted_months = sorted(monthly_groups.keys(), reverse=True)
            recent_months = sorted_months[:keep_monthly]

            for month_key in recent_months:
                first_of_month = min(monthly_groups[month_key], key=lambda x: x[1])
                protected_paths.add(first_of_month[0])

        to_delete = [path for path, _ in backup_items if path not in protected_paths]

        if to_delete:
            self.logger.info(
                f"Found {len(backup_items)} total backups ({len(protected_paths)} kept). Cleaning up {len(to_delete)} old backup(s)..."
            )

            for old_backup in to_delete:
                self.logger.info(f"Deleting old backup: {old_backup.name}")
                if not self.dry_run:
                    try:
                        if old_backup.is_dir():
                            shutil.rmtree(old_backup)
                        else:
                            old_backup.unlink()
                    except Exception as e:
                        self.error_count += 1
                        self.logger.error(f"Failed to delete '{old_backup}': {e}")
        else:
                        self.logger.info(f"No old backups to clean up ({len(backup_items)} total).")


def run_startup_backup(config_file: str = "paths.toml", force: bool = False, dry_run: bool = False) -> bool:
    backup_job = FileServerBackup(config_path=config_file, dry_run=dry_run, force=force)
    return backup_job.run_backup()


run_weekly_backup = run_startup_backup


def main():
    parser = argparse.ArgumentParser(description="Fileserver backup utility")
    parser.add_argument("-c", "--config", default="paths.toml", help="Path to paths.toml config")
    parser.add_argument("-f", "--force", action="store_true", help="Force backup run regardless of interval")
    parser.add_argument("--dry-run", action="store_true", help="Simulate backup without copying files")

    args = parser.parse_args()

    success = run_startup_backup(config_file=args.config, dry_run=args.dry_run, force=args.force)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
