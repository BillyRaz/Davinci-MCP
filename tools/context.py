"""Service container shared by MCP registration modules."""

from dataclasses import dataclass
from typing import Any

from resolve.capture import CaptureService
from resolve.clips import ClipService
from resolve.color import ColorService
from resolve.connection import ResolveConnection
from resolve.gallery import GalleryService
from resolve.grade import GradeWorkflow
from resolve.lut.application import LutApplicationService
from resolve.lut.installer import LutInstaller, resolve_lut_root
from resolve.lut.registry import LutRegistry
from resolve.markers import MarkerService
from resolve.media_pool import MediaPoolService
from resolve.nodes import NodeService
from resolve.output import OutputPaths
from resolve.platforms import detect_platform
from resolve.powergrade import PowerGradeCatalog
from resolve.project import ProjectService
from resolve.render import RenderService
from resolve.targeting import TimelineItemService
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
    targets: TimelineItemService
    lut_registry: LutRegistry
    lut_installer: LutInstaller
    lut_applications: LutApplicationService

    @classmethod
    def build(cls) -> "Services":
        connection = ResolveConnection()
        timelines = TimelineService(connection)
        colors = ColorService(connection)
        grades = PowerGradeCatalog(colors)
        output = OutputPaths()
        captures = CaptureService(connection, output)
        validation = ValidationService(connection, output, captures, grades)
        targets = TimelineItemService(connection, timelines)
        platform_paths = detect_platform()
        lut_registry = LutRegistry(output.directory("presets") / "luts.json")
        lut_installer = LutInstaller(
            resolve_lut_root(
                platform_paths.info.system, platform_paths.info.home_directory
            )
        )
        services = cls(
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
            lut_registry=lut_registry,
            lut_installer=lut_installer,
            lut_applications=None,  # type: ignore[arg-type]
        )
        services.lut_applications = LutApplicationService(services, lut_registry)
        return services


def register(mcp: Any, services: Services) -> None:
    from . import (
        capture_tools,
        gallery_tools,
        grade,
        inspect,
        lut_tools,
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
        lut_tools,
    ):
        module.register(mcp, services)
