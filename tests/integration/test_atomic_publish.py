from pathlib import Path

from inframap.publish.pipeline import atomic_publish


def test_atomic_publish_flips_latest_pointer(tmp_path: Path) -> None:
    staging_root = tmp_path / "staging"
    runs_root = tmp_path / "runs"
    published_root = tmp_path / "published"
    run_id = "run-test-123"

    staged = staging_root / run_id
    staged.mkdir(parents=True)
    (staged / "ok.txt").write_text("ok", encoding="utf-8")

    atomic_publish(
        run_id=run_id,
        staging_root=staging_root,
        runs_root=runs_root,
        published_root=published_root,
        blocking_checks_passed=True,
    )

    assert (runs_root / run_id / "ok.txt").exists()
    assert (published_root / "latest-dev").read_text(encoding="utf-8").strip() == run_id
    assert (published_root / "latest").read_text(encoding="utf-8").strip() == run_id


def test_atomic_publish_can_write_only_dev_pointer(tmp_path: Path) -> None:
    staging_root = tmp_path / "staging"
    runs_root = tmp_path / "runs"
    published_root = tmp_path / "published"
    run_id = "run-test-456"

    staged = staging_root / run_id
    staged.mkdir(parents=True)
    (staged / "ok.txt").write_text("ok", encoding="utf-8")

    atomic_publish(
        run_id=run_id,
        staging_root=staging_root,
        runs_root=runs_root,
        published_root=published_root,
        blocking_checks_passed=False,
        compatibility_alias=None,
    )

    assert (runs_root / run_id / "ok.txt").exists()
    assert (published_root / "latest-dev").read_text(encoding="utf-8").strip() == run_id
    assert not (published_root / "latest").exists()
