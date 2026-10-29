"""HTTP surface: status, config masking, path safety, jobs and SSE."""

import json
import re
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gamelink.resources import static_root
from gamelink.web import create_app

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "examples" / "snake-single"
VALID_PROTOCOL = (REPO / "examples" / "snake-specs" / "protocol.spec.yaml").read_text(
    encoding="utf-8"
)


@pytest.fixture
def workspace(tmp_path):
    return tmp_path


@pytest.fixture
def client(workspace):
    with TestClient(create_app(workspace)) as test_client:
        yield test_client


def wait_for_job(client, job_id, timeout=30.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        payload = client.get(f"/api/jobs/{job_id}").json()
        if payload["status"] not in ("queued", "running"):
            return payload
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} did not finish")


def test_health_reports_workspace_and_ui_state(client, workspace):
    payload = client.get("/api/health").json()
    assert payload["workspace"] == str(workspace.resolve())
    assert payload["ui_built"] is (static_root() / "index.html").is_file()
    assert "python" in payload
    assert set(payload["llm"]) == {"model", "base_url", "configured"}


def test_options_expose_choices_and_defaults(client):
    payload = client.get("/api/options").json()
    assert payload["choices"]["transport"] == ["enet", "websocket", "webrtc"]
    assert payload["defaults"]["max_players"] == 4


def test_schemas_by_name(client):
    protocol = client.get("/api/schemas/protocol").json()
    assert protocol["type"] == "object"
    assert client.get("/api/schemas/architecture.json").status_code == 200
    assert client.get("/api/schemas/nope").status_code == 404


def test_config_never_returns_the_api_key(client, monkeypatch):
    secret = "sk-do-not-leak-1234567890"
    monkeypatch.setenv("GAMELINK_LLM_API_KEY", secret)
    monkeypatch.setenv("GAMELINK_GODOT_BIN", "C:/D/GodotEngine/godot.exe")

    response = client.get("/api/config")
    payload = response.json()
    assert payload["has_key"] is True
    assert payload["godot_bin"] == "C:/D/GodotEngine/godot.exe"
    assert secret not in response.text
    assert "api_key" not in payload


def test_config_update_round_trip(client, tmp_path, monkeypatch):
    config_file = tmp_path / "config.json"
    monkeypatch.setattr("gamelink.config.user_config_path", lambda: config_file)
    monkeypatch.setattr("gamelink.web.routes.meta.user_config_path", lambda: config_file)
    monkeypatch.delenv("GAMELINK_LLM_MODEL", raising=False)

    assert client.put(
        "/api/config", json={"model": "deepseek-flash", "api_key": "sk-test"}
    ).status_code == 200

    stored = json.loads(config_file.read_text(encoding="utf-8"))
    assert stored["GAMELINK_LLM_MODEL"] == "deepseek-flash"
    assert stored["GAMELINK_LLM_API_KEY"] == "sk-test"
    assert client.get("/api/config").json()["has_key"] is True


def test_fs_lists_directories_and_flags_a_project(client, workspace):
    payload = client.get("/api/fs/dirs", params={"path": str(FIXTURE)}).json()
    assert payload["is_project"] is True
    assert payload["path"] == str(FIXTURE.resolve())
    assert client.get("/api/fs/dirs", params={"path": str(workspace)}).json()["is_project"] is False


def test_fs_entries_include_executables(client, tmp_path):
    folder = tmp_path / "engines"
    folder.mkdir()
    (folder / "Godot_v4.7.2-stable_win64_console.exe").write_text("x", encoding="utf-8")
    (folder / "notes.txt").write_text("x", encoding="utf-8")
    (folder / "nested").mkdir()

    payload = client.get("/api/fs/entries", params={"path": str(folder)}).json()
    assert [item["name"] for item in payload["files"]] == [
        "Godot_v4.7.2-stable_win64_console.exe"
    ]
    assert [item["name"] for item in payload["dirs"]] == ["nested"]
    assert "files" not in client.get("/api/fs/dirs", params={"path": str(folder)}).json()


def test_project_inspection(client, tmp_path):
    payload = client.get("/api/projects", params={"path": str(FIXTURE)}).json()
    assert payload["name"]
    assert payload["counts"]["scripts"] >= 1
    assert payload["file_tree"]

    bad = client.get("/api/projects", params={"path": str(tmp_path / "nope")})
    assert bad.status_code == 400
    assert "project.godot" in bad.json()["detail"]


def test_artifacts_reject_paths_outside_the_workspace(client):
    response = client.get("/api/artifacts", params={"path": "../../outside.yaml"})
    assert response.status_code == 403


def test_artifacts_reject_unknown_extensions(client, workspace):
    binary = workspace / "payload.exe"
    binary.write_bytes(b"MZ")
    assert client.get("/api/artifacts", params={"path": "payload.exe"}).status_code == 403


def test_artifact_write_validates_specs(client, workspace, tmp_path):
    target = workspace / "specs" / "protocol.spec.yaml"

    bad = client.put("/api/artifacts", json={"path": "specs/protocol.spec.yaml", "text": "not: [valid"})
    assert bad.status_code == 400
    assert "YAML" in bad.json()["detail"]
    assert not target.exists()

    invalid = client.put(
        "/api/artifacts", json={"path": "specs/protocol.spec.yaml", "text": "game: snake"}
    )
    assert invalid.status_code == 400
    assert not target.exists()

    assert client.put(
        "/api/artifacts",
        json={"path": "specs/protocol.spec.yaml", "text": VALID_PROTOCOL},
    ).status_code == 200
    assert client.get("/api/artifacts", params={"path": "specs/protocol.spec.yaml"}).json()[
        "text"
    ].startswith("game:")


def test_job_endpoint_validates_requests(client):
    assert client.post("/api/jobs", json={"kind": "teleport"}).status_code == 400
    assert client.post("/api/jobs", json={"kind": "analyze"}).status_code == 400
    assert client.get("/api/jobs/missing").status_code == 404
    assert client.post("/api/jobs/missing/cancel").status_code == 404


def test_job_runs_and_streams_over_sse(client):
    created = client.post("/api/jobs", json={"kind": "inspect", "params": {"project": str(FIXTURE)}})
    assert created.status_code == 200
    job_id = created.json()["id"]

    status = wait_for_job(client, job_id)
    assert status["status"] == "succeeded"

    response = client.get(f"/api/jobs/{job_id}/events")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    body = response.text
    assert "event: stage_started" in body
    assert "event: job_finished" in body
    assert "event: job_started" not in body

    tail = client.get(f"/api/jobs/{job_id}/events", params={"from_seq": 2}).text
    assert tail.count("data:") < body.count("data:")
    assert [item["id"] for item in client.get("/api/jobs").json()] == [job_id]


def test_cancel_endpoint_reports_state(client):
    created = client.post("/api/jobs", json={"kind": "inspect", "params": {"project": str(FIXTURE)}})
    job_id = created.json()["id"]
    wait_for_job(client, job_id)
    assert client.post(f"/api/jobs/{job_id}/cancel").json() == {"cancelled": False}


def test_host_guard_blocks_dns_rebinding(client):
    response = client.get("/api/health", headers={"host": "evil.example.com"})
    assert response.status_code == 403


def test_cross_origin_mutations_are_rejected(client):
    response = client.put(
        "/api/config",
        json={"model": "x"},
        headers={"origin": "https://evil.example.com"},
    )
    assert response.status_code == 403
    assert client.put(
        "/api/config", json={"model": "x"}, headers={"origin": "http://localhost:5173"}
    ).status_code == 200


def test_unknown_api_routes_do_not_fall_through_to_the_spa(client):
    assert client.get("/api/nope").status_code == 404


def test_spa_route_serves_the_built_ui_or_a_build_hint(client):
    response = client.get("/some/spa/route")
    if (static_root() / "index.html").is_file():
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
    else:
        assert response.status_code == 503
        assert "npm" in response.text


def test_built_ui_is_served_with_its_assets(client):
    index = static_root() / "index.html"
    if not index.is_file():
        pytest.skip("frontend not built")

    html = client.get("/").text
    references = re.findall(r'(?:src|href)="(/assets/[^"]+)"', html)
    assert references, "index.html references no built assets"
    for reference in references:
        assert client.get(reference).status_code == 200
