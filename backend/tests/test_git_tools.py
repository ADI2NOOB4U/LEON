from types import SimpleNamespace

import pytest

from backend.app.tools import git_tools
from backend.app.tools.registry import ToolRegistry


class FakeRepo:
    def get_walker(self, *, max_entries):
        assert max_entries == 2
        commit = SimpleNamespace(
            id=b"a1b2c3", message=b"Initial commit\n", author=b"LEON <leon@example.test>", commit_time=0
        )
        return [SimpleNamespace(commit=commit)]

    def get_refs(self):
        return {b"refs/heads/main": b"a1b2c3", b"refs/tags/v1": b"d4e5f6"}


class FakePorcelain:
    @staticmethod
    def status(repo):
        return SimpleNamespace(staged={b"add": [b"new.txt"]}, unstaged=[b"changed.txt"], untracked=[b"note.txt"])

    @staticmethod
    def diff(repo, *, outstream):
        outstream.write(b"diff --git a/a b/a\n")


@pytest.fixture
def repository(tmp_path, monkeypatch):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    monkeypatch.setattr(git_tools, "Repo", lambda path: FakeRepo())
    monkeypatch.setattr(git_tools, "porcelain", FakePorcelain)
    return repo_path


@pytest.mark.anyio
async def test_git_status_returns_structured_read_only_result(repository):
    result = await git_tools.GitStatusTool(allowed_roots=[repository.parent]).execute(repo_path="repo")

    assert result == {
        "tool": "git_status",
        "repo_path": str(repository),
        "staged": [{"status": "add", "path": "new.txt"}],
        "unstaged": ["changed.txt"],
        "untracked": ["note.txt"],
        "is_clean": False,
    }


@pytest.mark.anyio
async def test_git_log_validates_limit_and_returns_commits(repository):
    tool = git_tools.GitLogTool(allowed_roots=[repository.parent])
    result = await tool.execute(repo_path="repo", limit=2)

    assert result["count"] == 1
    assert result["commits"] == [{
        "id": "a1b2c3",
        "message": "Initial commit",
        "author": "LEON <leon@example.test>",
        "committed_at": "1970-01-01T00:00:00+00:00",
    }]
    with pytest.raises(ValueError, match="limit"):
        await tool.execute(repo_path="repo", limit=101)


@pytest.mark.anyio
async def test_git_diff_and_branches_use_library_results(repository):
    roots = [repository.parent]
    diff = await git_tools.GitDiffTool(allowed_roots=roots).execute(repo_path="repo")
    branches = await git_tools.GitBranchListTool(allowed_roots=roots).execute(repo_path="repo")

    assert diff["diff"] == "diff --git a/a b/a\n"
    assert diff["is_clean"] is False
    assert branches["branches"] == [{"name": "main", "commit": "a1b2c3"}]


@pytest.mark.anyio
async def test_git_tools_reject_paths_outside_leon_roots(tmp_path, monkeypatch):
    monkeypatch.setattr(git_tools, "Repo", lambda path: pytest.fail("repository must not be opened"))
    monkeypatch.setattr(git_tools, "porcelain", FakePorcelain)

    with pytest.raises(ValueError, match="configured LEON directory"):
        await git_tools.GitStatusTool(allowed_roots=[tmp_path / "allowed"]).execute(repo_path=str(tmp_path / "outside"))


def test_git_tools_register_as_safe():
    registry = ToolRegistry()
    git_tools.register_git_tools(registry)

    assert [tool.name for tool in registry.list()] == [
        "git_status", "git_log", "git_diff", "git_branch_list"
    ]
    assert all(tool.permission == "SAFE" for tool in registry.list())
