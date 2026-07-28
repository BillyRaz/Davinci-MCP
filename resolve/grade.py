"""High-level grading workflows backed by registered DRX templates."""

from typing import Any

from .errors import NotFoundError
from .powergrade import PowerGradeCatalog
from .timeline import TimelineService

LOOKS = {
    "cinematic": (
        "Input CST → Exposure → Contrast → HDR Wheels → Color Balance → "
        "Subject Isolation → Glow → Film Grain → Output CST"
    ),
    "luxury_bridal": (
        "Embroidery detail, warm golds, protected natural skin, soft bloom, "
        "cool shadows, and filmic contrast"
    ),
    "editorial": "Clean separation, controlled skin, crisp contrast, restrained saturation",
    "dark_moody": "Dense shadows, protected highlights, cool depth, selective warm skin",
    "music_video": "Stylized contrast, bold separation, glow, texture, and output transform",
    "commercial": "Neutral whites, accurate product color, clean skin, polished contrast",
}


class GradeWorkflow:
    """Apply authored grades without pretending the API can construct node graphs."""

    def __init__(self, catalog: PowerGradeCatalog, timelines: TimelineService) -> None:
        self.catalog = catalog
        self.timelines = timelines

    def create(
        self, look: str, track_index: int, item_index: int, grade_mode: int = 0
    ) -> dict[str, Any]:
        if look not in LOOKS:
            raise NotFoundError(f"Unknown look {look!r}; choose one of {sorted(LOOKS)}")
        result = self.catalog.apply(look, track_index, item_index, grade_mode)
        return {"look": look, "design": LOOKS[look], **result}

    def batch_apply(
        self, template: str, clips: list[dict[str, int]], grade_mode: int = 0
    ) -> dict[str, Any]:
        results = []
        for clip in clips:
            result = self.catalog.apply(
                template, clip["track_index"], clip["item_index"], grade_mode
            )
            results.append({**clip, **result})
        return {"template": template, "applied": len(results), "clips": results}
