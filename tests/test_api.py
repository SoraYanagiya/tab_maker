"""API の統合テスト（設計書 13.2）。"""

from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient

from app.api.projects import get_repository
from app.main import app
from app.repository.project_repository import ProjectRepository


@pytest.fixture
def client(tmp_path):
    app.dependency_overrides[get_repository] = lambda: ProjectRepository(tmp_path)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def note_list(midis: list[int]) -> dict:
    return {
        "notes": [
            {
                "midiNumber": midi,
                "pitchName": "C",
                "octave": 4,
                "onsetBeat": index % 4,
                "measureIndex": index // 4,
            }
            for index, midi in enumerate(midis)
        ],
        "measures": [{"measureIndex": 0}, {"measureIndex": 1}],
    }


class TestConvert:
    def test_converts_note_list_to_tab(self, client):
        response = client.post(
            "/api/convert",
            json={"inputType": "note_list", "content": note_list([60, 62, 64, 65])},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["tab"].splitlines()[0].lstrip().startswith("e|")
        assert len(body["fingerings"]) == 4
        assert all(f["stringIndex"] is not None for f in body["fingerings"])

    def test_details_are_optional(self, client):
        payload = {"inputType": "note_list", "content": note_list([60])}
        assert client.post("/api/convert", json=payload).json()["details"] is None
        payload["settings"] = {"includeDetails": True}
        assert "運指詳細" in client.post("/api/convert", json=payload).json()["details"]

    def test_custom_weights_are_applied(self, client):
        payload = {
            "inputType": "note_list",
            "content": note_list([60, 62, 64, 65, 67, 69, 71, 72]),
            "settings": {"weights": {"open_string_bonus": 0.0, "base_fret_preference": 5.0}},
        }
        response = client.post("/api/convert", json=payload)
        assert response.status_code == 200

    def test_rejects_malformed_note_list(self, client):
        response = client.post("/api/convert", json={"inputType": "note_list", "content": "oops"})
        assert response.status_code == 422

    def test_rejects_invalid_base64_midi(self, client):
        response = client.post("/api/convert", json={"inputType": "midi", "content": "not-base64!"})
        assert response.status_code == 422

    def test_converts_musicxml(self, client, musicxml_bytes):
        response = client.post(
            "/api/convert",
            json={"inputType": "musicxml", "content": musicxml_bytes.decode("utf-8")},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["notes"], "MusicXMLから読み取った音符が返る"
        assert body["tab"]


class TestImport:
    def test_imports_musicxml(self, client, musicxml_bytes):
        response = client.post(
            "/api/import",
            files={"file": ("melody.musicxml", musicxml_bytes, "application/xml")},
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body["notes"]) == 4
        assert body["measures"][0]["timeSignature"] == "4/4"

    def test_rejects_unknown_format(self, client):
        response = client.post("/api/import", files={"file": ("song.txt", b"x", "text/plain")})
        assert response.status_code == 422


class TestProjects:
    def test_crud_lifecycle(self, client):
        created = client.post("/api/projects", json={"name": "練習曲"})
        assert created.status_code == 201
        project_id = created.json()["projectId"]

        updated = client.put(
            f"/api/projects/{project_id}",
            json={"notes": note_list([60, 62])["notes"], "generatedTab": {"tab": "e|--"}},
        )
        assert updated.status_code == 200
        assert len(updated.json()["notes"]) == 2

        listed = client.get("/api/projects").json()
        assert listed[0]["name"] == "練習曲"
        assert listed[0]["noteCount"] == 2
        assert listed[0]["hasGeneratedTab"] is True

        assert client.get(f"/api/projects/{project_id}").json()["projectId"] == project_id
        assert client.delete(f"/api/projects/{project_id}").status_code == 204
        assert client.get("/api/projects").json() == []

    def test_duplicate_keeps_notes_and_creates_new_id(self, client):
        original = client.post(
            "/api/projects", json={"name": "原曲", "notes": note_list([60, 62])["notes"]}
        ).json()
        copy = client.post(
            f"/api/projects/{original['projectId']}/duplicate", json={"name": "別名保存"}
        ).json()
        assert copy["projectId"] != original["projectId"]
        assert copy["name"] == "別名保存"
        assert len(copy["notes"]) == 2

    def test_missing_project_returns_404(self, client):
        assert client.get("/api/projects/" + "0" * 32).status_code == 404
        assert client.put("/api/projects/" + "0" * 32, json={"name": "x"}).status_code == 404
        assert client.delete("/api/projects/" + "0" * 32).status_code == 404

    def test_invalid_project_id_is_not_a_path_traversal(self, client):
        assert client.get("/api/projects/..%2F..%2Fetc%2Fpasswd").status_code == 404
