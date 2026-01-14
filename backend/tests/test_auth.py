from fastapi.testclient import TestClient


def test_login_refresh_me_flow(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        json={"email": "demo@cloverbooks.local", "password": "changeme"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["access_token"]
    assert data["user"]["email"] == "demo@cloverbooks.local"

    me_response = client.get(
        "/me",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["user"]["email"] == "demo@cloverbooks.local"

    refresh_response = client.post("/auth/refresh")
    assert refresh_response.status_code == 200
    refresh_data = refresh_response.json()
    assert refresh_data["access_token"]

    me_again = client.get(
        "/me",
        headers={"Authorization": f"Bearer {refresh_data['access_token']}"},
    )
    assert me_again.status_code == 200


def test_invalid_login(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        json={"email": "wrong@example.com", "password": "nope"},
    )
    assert response.status_code == 401


def test_refresh_requires_cookie(client: TestClient) -> None:
    response = client.post("/auth/refresh")
    assert response.status_code == 401
