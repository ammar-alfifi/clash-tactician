"""Mirror the SQLite database to a private Git repository.

Render's free instances have no persistent disk, so the database is restored on
startup and pushed as a consistent snapshot. Failures are logged, never fatal.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import shutil
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

GITHUB_KNOWN_HOSTS = (
    "github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl\n"
    "github.com ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBEmKSENj"
    "QEezOmxkZMy7opKgwFB9nkt5YRrYMjNuG5N87uRgg6CLrbo5wAdT/y6v0mKV0U2w0WZ2YB/++Tpockg=\n"
    "github.com ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQCj7ndNxQowgcQnjshcLrqPEiiphnt+VTTvDP6mHBL9"
    "j1aNUkY4Ue1gvwnGLVlOhGeYrnZaMgRK6+PKCUXaDbC7qtbW8gIkhL7aGCsOr/C56SJMy/BCZfxd1nWzAOx"
    "SDPgVsmerOBYfNqltV9/hWCqBywINIR+5dIg6JTJ72pcEpEjcYgXkE2YEFXV1JHnsKgbLWNlhScqb2UmyR"
    "kQyytRLtL+38TGxkxCflmO+5Z8CSSNY7GidjMIZ7Q4zMjA2n1nGrlTDkzwDCsw+wqFPGQA179cnfGWOWR"
    "Vruj16z6XyvxvjJwbz0wQZ75XK5tKSb7FNyeIEs4TT4jk+S4dhPeAUC5y+bDYirYgM4GC7uEnztnZyaVWQ"
    "7B381AK4Qdrwt51ZqExKbQpTUNn+EjqoTwvqNj4kqx5QUCI0ThS/YkOxJCXmPUWZbhjpCg56i+2aB6CmK2J"
    "Ghn57K5mj0MNdBXA4/WnwH6XoPWJzK5Nyu2zB3nAZp+S5hpQs+p1vN1/wsjk=\n"
)

DEFAULT_INTERVAL_SECONDS = 900.0
GIT_TIMEOUT_SECONDS = 180


def _snapshot_sqlite(source: Path, destination: Path) -> None:
    if destination.exists():
        destination.unlink()
    connection = sqlite3.connect(source)
    try:
        connection.execute("VACUUM INTO ?", (str(destination),))
    finally:
        connection.close()


def _decode_key(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    try:
        return base64.b64decode(value).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return value


class DatabaseBackup:
    def __init__(
        self,
        database_path: Path,
        *,
        remote: str | None = None,
        private_key: str | None = None,
        interval_seconds: float | None = None,
    ) -> None:
        self.database_path = Path(database_path)
        self.remote = (remote if remote is not None else os.getenv("BACKUP_GIT_REMOTE", "")).strip()
        raw_key = private_key if private_key is not None else os.getenv("BACKUP_SSH_KEY", "")
        self.private_key = _decode_key(raw_key)
        if interval_seconds is not None:
            self.interval_seconds = interval_seconds
        else:
            raw = os.getenv("BACKUP_INTERVAL_SECONDS", "").strip()
            try:
                parsed = float(raw) if raw else DEFAULT_INTERVAL_SECONDS
            except ValueError:
                parsed = DEFAULT_INTERVAL_SECONDS
            self.interval_seconds = max(60.0, parsed)
        self._workdir: Path | None = None
        self._env: dict[str, str] | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.remote)

    def _base_workdir(self) -> Path:
        if self._workdir is None:
            self._workdir = Path(tempfile.mkdtemp(prefix="clash-backup-"))
        return self._workdir

    def _git_env(self) -> dict[str, str]:
        if self._env is not None:
            return self._env
        env = os.environ.copy()
        if self.private_key:
            workdir = self._base_workdir()
            key_path = workdir / "deploy_key"
            key_path.write_text(self.private_key, encoding="utf-8")
            key_path.chmod(0o600)
            known_hosts = workdir / "known_hosts"
            known_hosts.write_text(
                os.getenv("BACKUP_KNOWN_HOSTS", GITHUB_KNOWN_HOSTS), encoding="utf-8"
            )
            env["GIT_SSH_COMMAND"] = (
                f"ssh -i {key_path} -o IdentitiesOnly=yes "
                f"-o UserKnownHostsFile={known_hosts} -o StrictHostKeyChecking=yes"
            )
        self._env = env
        return env

    async def _git(self, *args: str, cwd: Path) -> tuple[int, str]:
        process = await asyncio.create_subprocess_exec(
            "git",
            *args,
            cwd=cwd,
            env=self._git_env(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(), GIT_TIMEOUT_SECONDS)
        except TimeoutError:
            process.kill()
            await process.wait()
            return 124, "git command timed out"
        return process.returncode or 0, stdout.decode(errors="replace")

    async def _clone(self) -> Path | None:
        target = self._base_workdir() / "repo"
        if (target / ".git").exists():
            return target
        code, output = await self._git(
            "clone", "--depth", "1", self.remote, str(target), cwd=self._base_workdir()
        )
        if code != 0:
            logger.warning("Database backup clone failed: %s", output.strip()[:500])
            return None
        return target

    async def restore(self) -> bool:
        if not self.enabled:
            return False
        if self.database_path.exists() and self.database_path.stat().st_size > 0:
            return False
        repo = await self._clone()
        if repo is None:
            return False
        source = repo / self.database_path.name
        if not source.exists() or source.stat().st_size == 0:
            logger.info("No database backup found to restore")
            return False
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, self.database_path)
        logger.info("Restored database backup (%d bytes)", self.database_path.stat().st_size)
        return True

    async def backup_once(self) -> bool:
        if not self.enabled or not self.database_path.exists():
            return False
        repo = await self._clone()
        if repo is None:
            return False
        snapshot = self._base_workdir() / "snapshot.sqlite3"
        try:
            await asyncio.to_thread(_snapshot_sqlite, self.database_path, snapshot)
        except (sqlite3.Error, OSError):
            logger.warning("Could not snapshot the database", exc_info=True)
            return False
        shutil.copyfile(snapshot, repo / self.database_path.name)
        await self._git("add", self.database_path.name, cwd=repo)
        message = datetime.now(UTC).strftime("backup %Y-%m-%d %H:%M:%S UTC")
        code, output = await self._git(
            "-c",
            "user.name=clash-tactician",
            "-c",
            "user.email=backup@localhost",
            "commit",
            "-m",
            message,
            cwd=repo,
        )
        if code != 0:
            if "nothing to commit" in output:
                return True
            logger.warning("Database backup commit failed: %s", output.strip()[:500])
            return False
        code, output = await self._git("push", "origin", "HEAD", cwd=repo)
        if code != 0:
            logger.warning("Database backup push failed: %s", output.strip()[:500])
            return False
        logger.info("Database backup pushed")
        return True

    async def run(self) -> None:
        while True:
            await asyncio.sleep(self.interval_seconds)
            await self.backup_once()
