"""Read-only Git tools backed by the pure-Python Dulwich library."""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

try:
    from dulwich import porcelain
    from dulwich.errors import NotGitRepository
    from dulwich.repo import Repo
except ImportError:  # Allows unrelated LEON features to start before setup completes.
    porcelain = None
    NotGitRepository = Exception
    Repo = None

from backend.app.tools.filesystem_tools import FilesystemTool
from backend.app.tools.registry import ToolRegistry


def _text(value: bytes | str) -> str:
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value


class GitTool(FilesystemTool):
    """Base class which permits only existing repositories in LEON roots."""

    def _repository(self, repo_path: str) -> tuple[Path, Any]:
        path = self._resolve_path(repo_path)
        if not path.is_dir():
            raise ValueError("repo_path must be an existing directory")
        if Repo is None or porcelain is None:
            raise RuntimeError("Dulwich is not installed. Run: pip install -r backend/requirements.txt")
        try:
            return path, Repo(str(path))
        except NotGitRepository as exc:
            raise ValueError("repo_path must be a Git repository") from exc


class GitStatusTool(GitTool):
    name = "git_status"
    description = "Return read-only Git working-tree status for a LEON repository."
    permission = "SAFE"

    async def execute(self, repo_path: str = "", **kwargs: Any) -> dict[str, Any]:
        if kwargs:
            raise ValueError("git_status received unexpected arguments")
        path, repo = self._repository(repo_path)
        status = porcelain.status(repo)
        staged = [
            {"status": _text(kind), "path": _text(item)}
            for kind, items in status.staged.items()
            for item in items
        ]
        return {
            "tool": self.name,
            "repo_path": str(path),
            "staged": staged,
            "unstaged": [_text(item) for item in status.unstaged],
            "untracked": [_text(item) for item in status.untracked],
            "is_clean": not staged and not status.unstaged and not status.untracked,
        }


class GitLogTool(GitTool):
    name = "git_log"
    description = "Return recent commits from a LEON repository."
    permission = "SAFE"

    async def execute(
        self, repo_path: str = "", limit: int = 10, **kwargs: Any
    ) -> dict[str, Any]:
        if kwargs:
            raise ValueError("git_log received unexpected arguments")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("limit must be an integer between 1 and 100")

        path, repo = self._repository(repo_path)
        commits = []
        for entry in repo.get_walker(max_entries=limit):
            commit = entry.commit
            commits.append(
                {
                    "id": _text(commit.id),
                    "message": _text(commit.message).rstrip("\n"),
                    "author": _text(commit.author),
                    "committed_at": datetime.fromtimestamp(
                        commit.commit_time, tz=timezone.utc
                    ).isoformat(),
                }
            )
        return {"tool": self.name, "repo_path": str(path), "commits": commits, "count": len(commits)}


class GitDiffTool(GitTool):
    name = "git_diff"
    description = "Return the read-only working-tree diff for a LEON repository."
    permission = "SAFE"

    async def execute(self, repo_path: str = "", **kwargs: Any) -> dict[str, Any]:
        if kwargs:
            raise ValueError("git_diff received unexpected arguments")
        path, repo = self._repository(repo_path)
        output = BytesIO()
        # Dulwich reads the worktree directly; it does not execute git or a shell.
        porcelain.diff(repo, outstream=output)
        diff = output.getvalue().decode("utf-8", errors="replace")
        return {"tool": self.name, "repo_path": str(path), "diff": diff, "is_clean": not diff}


class GitBranchListTool(GitTool):
    name = "git_branch_list"
    description = "List local branches in a LEON repository."
    permission = "SAFE"

    async def execute(self, repo_path: str = "", **kwargs: Any) -> dict[str, Any]:
        if kwargs:
            raise ValueError("git_branch_list received unexpected arguments")
        path, repo = self._repository(repo_path)
        prefix = b"refs/heads/"
        branches = [
            {"name": _text(ref[len(prefix) :]), "commit": _text(commit_id)}
            for ref, commit_id in repo.get_refs().items()
            if ref.startswith(prefix)
        ]
        branches.sort(key=lambda branch: branch["name"])
        return {"tool": self.name, "repo_path": str(path), "branches": branches, "count": len(branches)}


def register_git_tools(registry: ToolRegistry) -> ToolRegistry:
    """Register the read-only Git tools."""
    registry.register(GitStatusTool())
    registry.register(GitLogTool())
    registry.register(GitDiffTool())
    registry.register(GitBranchListTool())
    return registry
