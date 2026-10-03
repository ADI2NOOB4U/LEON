from pathlib import Path
from typing import Any, Iterable

from backend.app.config.settings import settings
from backend.app.tools.base import BaseTool
from backend.app.tools.registry import ToolRegistry


class FilesystemTool(BaseTool):
    """Base class for tools restricted to LEON-managed directories."""

    def __init__(self, allowed_roots: Iterable[Path] | None = None) -> None:
        roots = allowed_roots or (settings.workspace_dir, settings.data_dir)
        self._allowed_roots = tuple(Path(root).resolve() for root in roots)
        self._workspace_root = self._allowed_roots[0]

    def _resolve_path(self, path: str) -> Path:
        if not isinstance(path, str) or not path.strip():
            raise ValueError("path must be a non-empty string")
        if "\x00" in path:
            raise ValueError("path must not contain null bytes")

        requested = Path(path)
        if not requested.is_absolute():
            requested = self._workspace_root / requested
        resolved = requested.resolve(strict=False)
        if not any(resolved.is_relative_to(root) for root in self._allowed_roots):
            raise ValueError("path must be inside a configured LEON directory")
        return resolved


class ListDirectoryTool(FilesystemTool):
    name = "list_directory"
    description = "List entries in a LEON workspace or data directory."
    permission = "SAFE"

    async def execute(self, path: str = "", **kwargs: Any) -> dict[str, Any]:
        if kwargs:
            raise ValueError("list_directory received unexpected arguments")

        directory = self._resolve_path(path)
        if not directory.is_dir():
            raise ValueError("path must be an existing directory")

        entries = []
        for entry in sorted(directory.iterdir(), key=lambda item: item.name.casefold()):
            entry_type = "symlink" if entry.is_symlink() else "directory" if entry.is_dir() else "file"
            entries.append({"name": entry.name, "type": entry_type})
        return {
            "tool": self.name,
            "path": str(directory),
            "entries": entries,
            "count": len(entries),
        }


class ReadFileTool(FilesystemTool):
    name = "read_file"
    description = "Read a UTF-8 file from a LEON workspace or data directory."
    permission = "SAFE"

    async def execute(self, path: str = "", **kwargs: Any) -> dict[str, Any]:
        if kwargs:
            raise ValueError("read_file received unexpected arguments")

        file_path = self._resolve_path(path)
        if not file_path.is_file():
            raise ValueError("path must be an existing file")
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("file must be UTF-8 text") from exc
        return {"tool": self.name, "path": str(file_path), "content": content}


class CreateFileTool(FilesystemTool):
    name = "create_file"
    description = "Create a new UTF-8 file in a LEON workspace or data directory."
    permission = "CONFIRM"

    async def execute(
        self, path: str = "", content: str = "", **kwargs: Any
    ) -> dict[str, Any]:
        if kwargs:
            raise ValueError("create_file received unexpected arguments")
        if not isinstance(content, str):
            raise ValueError("content must be a string")

        file_path = self._resolve_path(path)
        if not file_path.parent.is_dir():
            raise ValueError("parent directory must already exist")
        try:
            with file_path.open("x", encoding="utf-8") as file:
                file.write(content)
        except FileExistsError as exc:
            raise ValueError("file already exists and will not be overwritten") from exc
        return {
            "tool": self.name,
            "path": str(file_path),
            "created": True,
            "bytes_written": len(content.encode("utf-8")),
        }


class EditFileTool(FilesystemTool):
    name = "edit_file"
    description = "Replace the UTF-8 contents of an existing LEON workspace or data file."
    permission = "CONFIRM"

    async def execute(
        self, path: str = "", content: str = "", **kwargs: Any
    ) -> dict[str, Any]:
        if kwargs:
            raise ValueError("edit_file received unexpected arguments")
        if not isinstance(content, str):
            raise ValueError("content must be a string")

        file_path = self._resolve_path(path)
        if not file_path.is_file():
            raise ValueError("path must be an existing file")
        try:
            file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("file must be UTF-8 text") from exc
        file_path.write_text(content, encoding="utf-8")
        return {
            "tool": self.name,
            "path": str(file_path),
            "edited": True,
            "bytes_written": len(content.encode("utf-8")),
        }


class CreateDirectoryTool(FilesystemTool):
    name = "create_directory"
    description = "Create a new directory in a LEON workspace or data directory."
    permission = "CONFIRM"

    async def execute(self, path: str = "", **kwargs: Any) -> dict[str, Any]:
        if kwargs:
            raise ValueError("create_directory received unexpected arguments")

        directory = self._resolve_path(path)
        if not directory.parent.is_dir():
            raise ValueError("parent directory must already exist")
        try:
            directory.mkdir()
        except FileExistsError as exc:
            raise ValueError("directory already exists") from exc
        return {"tool": self.name, "path": str(directory), "created": True}


def register_filesystem_tools(registry: ToolRegistry) -> ToolRegistry:
    """Register filesystem tools restricted to LEON-managed directories."""
    registry.register(ListDirectoryTool())
    registry.register(ReadFileTool())
    registry.register(CreateFileTool())
    registry.register(EditFileTool())
    registry.register(CreateDirectoryTool())
    return registry
