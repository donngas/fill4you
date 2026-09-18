from fastapi.testclient import TestClient


def test_privacy_policy_is_public_and_discloses_google_calendar_use(client: TestClient) -> None:
    response = client.get("/privacy")

    assert response.status_code == 200
    assert "개인정보처리방침" in response.text
    assert "Google Calendar" in response.text
