"""Recursive media-pool browsing and search."""

from typing import Any

from .connection import ResolveConnection
from .errors import NotFoundError, OperationError


class MediaPoolService:
    def __init__(self, connection: ResolveConnection) -> None:
        self.connection = connection

    def _folder(self, folder: Any, include_clips: bool) -> dict[str, Any]:
        result = {
            "name": folder.GetName(),
            "unique_id": folder.GetUniqueId(),
            "folders": [self._folder(child, include_clips) for child in folder.GetSubFolderList()],
        }
        if include_clips:
            result["clips"] = [
                {
                    "name": clip.GetName(),
                    "unique_id": clip.GetUniqueId(),
                    "properties": clip.GetClipProperty(),
                }
                for clip in folder.GetClipList()
            ]
        return result

    def tree(self, include_clips: bool = True) -> dict[str, Any]:
        root = self.connection.project().GetMediaPool().GetRootFolder()
        if root is None:
            raise OperationError("Resolve did not return the media-pool root")
        return self._folder(root, include_clips)

    def search(self, query: str) -> list[dict[str, Any]]:
        needle = query.casefold()
        matches: list[dict[str, Any]] = []

        def visit(folder: Any, path: str) -> None:
            here = f"{path}/{folder.GetName()}"
            for clip in folder.GetClipList():
                props = clip.GetClipProperty()
                if needle in clip.GetName().casefold() or any(
                    needle in str(value).casefold() for value in props.values()
                ):
                    matches.append(
                        {"name": clip.GetName(), "unique_id": clip.GetUniqueId(), "bin": here}
                    )
            for child in folder.GetSubFolderList():
                visit(child, here)

        root = self.connection.project().GetMediaPool().GetRootFolder()
        if root is None:
            raise NotFoundError("Media-pool root is unavailable")
        visit(root, "")
        return matches
