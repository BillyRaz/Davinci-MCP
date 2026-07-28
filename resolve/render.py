"""Render-preset, queue, start, and monitoring operations."""

from typing import Any

from .connection import ResolveConnection
from .errors import NotFoundError, OperationError, ValidationError
from .models import RenderSettings


class RenderService:
    def __init__(self, connection: ResolveConnection) -> None:
        self.connection = connection

    def presets(self) -> list[Any]:
        return self.connection.project().GetRenderPresetList() or []

    def configure(self, settings: RenderSettings) -> dict[str, Any]:
        project = self.connection.project()
        if settings.preset and not project.LoadRenderPreset(settings.preset):
            raise NotFoundError(f"Render preset {settings.preset!r} was not found")
        if (settings.format is None) != (settings.codec is None):
            raise ValidationError("format and codec must be supplied together")
        if settings.format and not project.SetCurrentRenderFormatAndCodec(
            settings.format, settings.codec
        ):
            raise ValidationError(
                f"Unsupported format/codec combination: {settings.format}/{settings.codec}"
            )
        if not project.SetCurrentRenderMode(1 if settings.mode == "single" else 0):
            raise OperationError("Resolve could not set the render mode")
        payload = {
            "TargetDir": settings.target_dir,
            "CustomName": settings.custom_name,
            "ExportVideo": settings.export_video,
            "ExportAudio": settings.export_audio,
        }
        if not project.SetRenderSettings(payload):
            raise OperationError("Resolve rejected the render settings")
        return {
            **payload,
            **(project.GetCurrentRenderFormatAndCodec() or {}),
            "mode": settings.mode,
        }

    def save_preset(self, name: str) -> dict[str, str]:
        if not self.connection.project().SaveAsNewRenderPreset(name):
            raise OperationError(f"Could not save render preset {name!r}; it may already exist")
        return {"preset": name}

    def add_job(self) -> dict[str, str]:
        job_id = self.connection.project().AddRenderJob()
        if not job_id:
            raise OperationError("Resolve could not add a render job")
        return {"job_id": job_id}

    def jobs(self) -> list[Any]:
        return self.connection.project().GetRenderJobList() or []

    def start(self, job_ids: list[str] | None = None) -> dict[str, Any]:
        project = self.connection.project()
        ok = project.StartRendering(job_ids, False) if job_ids else project.StartRendering(False)
        if not ok:
            raise OperationError("Resolve could not start rendering")
        return {"started": job_ids or "all"}

    def status(self, job_id: str | None = None) -> dict[str, Any]:
        project = self.connection.project()
        if job_id:
            status = project.GetRenderJobStatus(job_id)
            if not status:
                raise NotFoundError(f"Render job {job_id!r} was not found")
            return status
        return {
            "rendering": project.IsRenderingInProgress(),
            "jobs": project.GetRenderJobList() or [],
        }
