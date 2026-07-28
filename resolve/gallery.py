"""Gallery still and PowerGrade album operations."""

from pathlib import Path
from typing import Any

from .connection import ResolveConnection
from .errors import NotFoundError, OperationError, ValidationError


class GalleryService:
    def __init__(self, connection: ResolveConnection) -> None:
        self.connection = connection

    def _gallery(self) -> Any:
        gallery = self.connection.project().GetGallery()
        if gallery is None:
            raise OperationError("Gallery is unavailable")
        return gallery

    def albums(self, powergrades: bool = False) -> list[dict[str, Any]]:
        gallery = self._gallery()
        source = (
            gallery.GetGalleryPowerGradeAlbums()
            if powergrades
            else gallery.GetGalleryStillAlbums()
        )
        return [
            {
                "index": index,
                "name": gallery.GetAlbumName(album),
                "still_count": len(album.GetStills() or []),
                "powergrade": powergrades,
            }
            for index, album in enumerate(source or [], 1)
        ]

    def _album(self, index: int, powergrades: bool = False) -> Any:
        gallery = self._gallery()
        albums = (
            gallery.GetGalleryPowerGradeAlbums()
            if powergrades
            else gallery.GetGalleryStillAlbums()
        ) or []
        if index < 1 or index > len(albums):
            raise NotFoundError(f"Gallery album index {index} was not found")
        return albums[index - 1]

    def stills(self, album_index: int, powergrades: bool = False) -> list[dict[str, Any]]:
        album = self._album(album_index, powergrades)
        return [
            {"index": index, "label": album.GetLabel(still)}
            for index, still in enumerate(album.GetStills() or [], 1)
        ]

    def grab(self, label: str = "") -> dict[str, Any]:
        still = self.connection.timeline().GrabStill()
        if still is None:
            raise OperationError("Resolve could not grab a still; open the Color page on a clip")
        album = self._gallery().GetCurrentStillAlbum()
        if label and not album.SetLabel(still, label):
            raise OperationError("Still was grabbed but could not be labelled")
        return {"label": label}

    def export(
        self,
        album_index: int,
        still_indices: list[int],
        folder: str,
        prefix: str,
        format: str = "drx",
        powergrades: bool = False,
    ) -> dict[str, Any]:
        if format not in {"dpx", "cin", "tif", "jpg", "png", "ppm", "bmp", "xpm", "drx"}:
            raise ValidationError(f"Unsupported still export format: {format}")
        target = Path(folder).expanduser()
        if not target.is_dir():
            raise ValidationError(f"Export folder does not exist: {target}")
        album = self._album(album_index, powergrades)
        stills = album.GetStills() or []
        try:
            chosen = [stills[index - 1] for index in still_indices]
        except IndexError as exc:
            raise NotFoundError("One or more still indices do not exist") from exc
        before = set(target.iterdir())
        if not album.ExportStills(chosen, str(target), prefix, format):
            raise OperationError("Resolve could not export the selected stills")
        created_paths = sorted(
            str(path.resolve())
            for path in set(target.iterdir()) - before
            if path.is_file()
        )
        return {
            "count": len(chosen),
            "folder": str(target.resolve()),
            "format": format,
            "created_paths": created_paths,
        }

    def apply_still(self, *_: Any) -> None:
        raise OperationError(
            "The official Gallery API cannot directly apply an in-memory still. "
            "Export it as DRX, then use apply_grade."
        )
