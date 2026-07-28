"""Timeline inspection and item addressing."""

from typing import Any

from .connection import ResolveConnection
from .errors import NotFoundError, ValidationError


class TimelineService:
    def __init__(self, connection: ResolveConnection) -> None:
        self.connection = connection

    def current(self) -> dict[str, Any]:
        timeline = self.connection.timeline()
        return {
            "name": timeline.GetName(),
            "unique_id": timeline.GetUniqueId(),
            "start_frame": timeline.GetStartFrame(),
            "end_frame": timeline.GetEndFrame(),
            "start_timecode": timeline.GetStartTimecode(),
            "playhead_timecode": timeline.GetCurrentTimecode(),
            "video_tracks": timeline.GetTrackCount("video"),
            "audio_tracks": timeline.GetTrackCount("audio"),
        }

    def clips(self, track_index: int | None = None) -> list[dict[str, Any]]:
        timeline = self.connection.timeline()
        tracks = (
            [track_index]
            if track_index is not None
            else range(1, timeline.GetTrackCount("video") + 1)
        )
        output: list[dict[str, Any]] = []
        for track in tracks:
            if track < 1 or track > timeline.GetTrackCount("video"):
                raise ValidationError(f"Video track {track} does not exist")
            for index, item in enumerate(timeline.GetItemListInTrack("video", track) or [], 1):
                media = item.GetMediaPoolItem()
                output.append(
                    {
                        "track_index": track,
                        "item_index": index,
                        "name": item.GetName(),
                        "unique_id": item.GetUniqueId(),
                        "start": item.GetStart(),
                        "end": item.GetEnd(),
                        "duration": item.GetDuration(),
                        "enabled": item.GetClipEnabled(),
                        "media_pool_id": media.GetUniqueId() if media else None,
                    }
                )
        return output

    def item(self, track_index: int, item_index: int) -> Any:
        timeline = self.connection.timeline()
        items = timeline.GetItemListInTrack("video", track_index) or []
        if item_index < 1 or item_index > len(items):
            raise NotFoundError(
                f"Video item {item_index} does not exist on track {track_index}"
            )
        return items[item_index - 1]

    def current_item(self) -> Any:
        item = self.connection.timeline().GetCurrentVideoItem()
        if item is None:
            raise NotFoundError("There is no video clip under the current playhead")
        return item

    def jump(self, timecode: str) -> dict[str, str]:
        if not self.connection.timeline().SetCurrentTimecode(timecode):
            raise ValidationError(f"Resolve rejected timecode {timecode!r}")
        return {"timecode": timecode}
