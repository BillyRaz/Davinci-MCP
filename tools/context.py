"""Service container shared by MCP registration modules."""

from dataclasses import dataclass
from typing import Any

from resolve.capture import CaptureService
from resolve.clips import ClipService
from resolve.color import ColorService
from resolve.connection import ResolveConnection
from resolve.gallery import GalleryService
from resolve.grade import GradeWorkflow
from resolve.markers import MarkerService
from resolve.media_pool import MediaPoolService
from resolve.nodes import NodeService
from resolve.output import OutputPaths
from resolve.powergrade import PowerGradeCatalog
from resolve.project import ProjectService
from resolve.render import RenderService
from resolve.targeting import TimelineTargetService
from resolve.timeline import TimelineService
from resolve.validation import ValidationService


@dataclass(slots=True)
class Services:
    connection: ResolveConnection
    projects: ProjectService
    timelines: TimelineService
    clips: ClipService
    colors: ColorService
    nodes: NodeService
    markers: MarkerService
    media: MediaPoolService
    renders: RenderService
    gallery: GalleryService
    grades: PowerGradeCatalog
    workflows: GradeWorkflow
    captures: CaptureService
    validation: ValidationService
    targets: TimelineTargetService

    @classmethod
    def build(cls) -> "Services":
        connection = ResolveConnection()
        timelines = TimelineService(connection)
        colors = ColorService(connection)
        grades = PowerGradeCatalog(colors)
        output = OutputPaths()
        captures = CaptureService(connection, output)
        validation = ValidationService(connection, output, captures, grades)
        targets = TimelineTargetService(connection, timelines)
        return cls(
            connection=connection,
            projects=ProjectService(connection),
            timelines=timelines,
            clips=ClipService(connection),
            colors=colors,
            nodes=NodeService(connection),
            markers=MarkerService(connection),
            media=MediaPoolService(connection),
            renders=RenderService(connection),
            gallery=GalleryService(connection),
            grades=grades,
            workflows=GradeWorkflow(grades, timelines),
            captures=captures,
            validation=validation,
            targets=targets,
        )


def register(mcp: Any, services: Services) -> None:
    from . import (
        capture_tools,
        gallery_tools,
        grade,
        inspect,
        node_tools,
        render_tools,
        target_tools,
        timeline_tools,
        validation_tools,
    )

    for module in (
        inspect,
        timeline_tools,
        target_tools,
        node_tools,
        grade,
        render_tools,
        gallery_tools,
        capture_tools,
        validation_tools,
    ):
        module.register(mcp, services)
