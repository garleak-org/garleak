from fastapi.testclient import TestClient

from garleak_api.worker import ping


def test_healthz(client: TestClient) -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "garleak-api"


def test_ping_task_runs_eagerly() -> None:
    # apply() executes in-process, so no broker is needed.
    assert ping.apply().get() == "pong"
