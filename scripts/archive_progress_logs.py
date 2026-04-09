from __future__ import annotations

import argparse
import shutil
from datetime import UTC, date, datetime, timedelta
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Archive stale committed progress logs.")
    parser.add_argument("--days", type=int, default=7, help="Archive logs older than this many days.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned moves without changing files.")
    return parser.parse_args()


def iter_archivable_logs(progress_root: Path, cutoff_date: date):
    for path in sorted(progress_root.glob("*.md")):
        prefix = path.stem.split("-", 3)[:3]
        if len(prefix) != 3:
            continue
        try:
            created_on = datetime.strptime("-".join(prefix), "%Y-%m-%d").date()
        except ValueError:
            continue
        if created_on < cutoff_date:
            yield path


def archive_progress_logs(days: int, dry_run: bool) -> tuple[int, list[tuple[Path, Path]]]:
    progress_root = Path("logs/progress")
    archive_root = Path("archive/logs/progress")
    archive_root.mkdir(parents=True, exist_ok=True)
    cutoff_date = (datetime.now(UTC) - timedelta(days=days)).date()
    planned_moves: list[tuple[Path, Path]] = []

    for source in iter_archivable_logs(progress_root, cutoff_date):
        target = archive_root / source.name
        planned_moves.append((source, target))
        if dry_run:
            continue
        shutil.move(str(source), str(target))

    return len(planned_moves), planned_moves


def main() -> int:
    args = parse_args()
    count, moves = archive_progress_logs(days=args.days, dry_run=args.dry_run)
    mode = "Would archive" if args.dry_run else "Archived"
    print(f"{mode} {count} progress log(s).")
    for source, target in moves:
        print(f"{source} -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
