import sqlite3
import subprocess
from pathlib import Path

from app.persistence import DatabaseBackup, _snapshot_sqlite


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def _create_seed_remote(tmp_path: Path) -> str:
    bare = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", "-b", "main", str(bare)],
        check=True,
        capture_output=True,
    )
    seed = tmp_path / "seed"
    seed.mkdir()
    _git("init", "-b", "main", cwd=seed)
    _git("config", "user.name", "seed", cwd=seed)
    _git("config", "user.email", "seed@example.com", cwd=seed)
    (seed / "README.md").write_text("backup store\n", encoding="utf-8")
    _git("add", "README.md", cwd=seed)
    _git("commit", "-m", "init", cwd=seed)
    _git("remote", "add", "origin", str(bare), cwd=seed)
    _git("push", "-u", "origin", "main", cwd=seed)
    return f"file://{bare}"


def _create_database(path: Path, value: str) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute("CREATE TABLE IF NOT EXISTS entries (value TEXT)")
        connection.execute("INSERT INTO entries (value) VALUES (?)", (value,))
        connection.commit()
    finally:
        connection.close()


def test_snapshot_sqlite_is_readable(tmp_path: Path) -> None:
    source = tmp_path / "bot.sqlite3"
    _create_database(source, "hello")
    destination = tmp_path / "snapshot.sqlite3"

    _snapshot_sqlite(source, destination)

    connection = sqlite3.connect(destination)
    try:
        assert connection.execute("SELECT value FROM entries").fetchone() == ("hello",)
    finally:
        connection.close()


async def test_backup_and_restore_roundtrip(tmp_path: Path) -> None:
    remote = _create_seed_remote(tmp_path)
    database_path = tmp_path / "data" / "bot.sqlite3"
    database_path.parent.mkdir()
    _create_database(database_path, "clan")

    backup = DatabaseBackup(database_path, remote=remote, interval_seconds=0)
    assert await backup.backup_once() is True

    database_path.unlink()
    assert await backup.restore() is True

    connection = sqlite3.connect(database_path)
    try:
        assert connection.execute("SELECT value FROM entries").fetchone() == ("clan",)
    finally:
        connection.close()


async def test_restore_skips_when_database_exists(tmp_path: Path) -> None:
    remote = _create_seed_remote(tmp_path)
    database_path = tmp_path / "data" / "bot.sqlite3"
    database_path.parent.mkdir()
    _create_database(database_path, "local")

    backup = DatabaseBackup(database_path, remote=remote, interval_seconds=0)
    assert await backup.restore() is False


async def test_disabled_without_remote(tmp_path: Path) -> None:
    backup = DatabaseBackup(tmp_path / "bot.sqlite3", remote="", private_key="")
    assert backup.enabled is False
    assert await backup.backup_once() is False
