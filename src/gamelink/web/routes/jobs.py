"""Job submission, status, event streaming and cancellation."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from gamelink.pipeline.jobs import Job, JobManager
from gamelink.web.sse import SSE_HEADERS, frames

router = APIRouter(prefix="/api")


def manager(request: Request) -> JobManager:
    return request.app.state.jobs


def _job(request: Request, job_id: str) -> Job:
    job = manager(request).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"没有这个任务：{job_id}")
    return job


class JobRequest(BaseModel):
    kind: str
    params: dict[str, Any] = Field(default_factory=dict)


@router.post("/jobs")
def submit(request: Request, payload: JobRequest) -> dict[str, Any]:
    try:
        job = manager(request).submit(payload.kind, payload.params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return job.to_dict()


@router.get("/jobs")
def list_jobs(request: Request, limit: int = 50) -> list[dict[str, Any]]:
    return [job.to_dict() for job in manager(request).list(limit)]


@router.get("/jobs/{job_id}")
def get_job(request: Request, job_id: str) -> dict[str, Any]:
    return _job(request, job_id).to_dict()


@router.get("/jobs/{job_id}/events")
def job_events(request: Request, job_id: str, from_seq: int = 0) -> StreamingResponse:
    jobs = manager(request)
    job = _job(request, job_id)
    return StreamingResponse(
        frames(jobs.stream(job, from_seq=from_seq)),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.post("/jobs/{job_id}/cancel")
def cancel_job(request: Request, job_id: str) -> dict[str, Any]:
    jobs = manager(request)
    _job(request, job_id)
    return {"cancelled": jobs.cancel(job_id)}
