from pathlib import Path
import importlib.util


def _load_archive_progress_logs():
    module_path = Path("scripts/archive_progress_logs.py")
    spec = importlib.util.spec_from_file_location("archive_progress_logs", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.archive_progress_logs


def test_archive_progress_logs_moves_old_files(tmp_path: Path, monkeypatch) -> None:
    archive_progress_logs = _load_archive_progress_logs()
    monkeypatch.chdir(tmp_path)
    progress_root = Path("logs/progress")
    archive_root = Path("archive/logs/progress")
    progress_root.mkdir(parents=True, exist_ok=True)
    archive_root.mkdir(parents=True, exist_ok=True)

    old_log = progress_root / "2026-01-01-old-task.md"
    recent_log = progress_root / "2026-04-09-recent-task.md"
    old_log.write_text("old", encoding="utf-8")
    recent_log.write_text("recent", encoding="utf-8")

    count, moves = archive_progress_logs(days=7, dry_run=False)

    assert count == 1
    assert moves == [(old_log, archive_root / old_log.name)]
    assert not old_log.exists()
    assert (archive_root / old_log.name).exists()
    assert recent_log.exists()
