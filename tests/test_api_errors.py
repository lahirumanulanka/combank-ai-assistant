def test_every_response_has_a_request_id(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]


def test_request_id_from_caller_is_kept(client):
    response = client.get("/health", headers={"X-Request-ID": "abc123"})

    assert response.headers["X-Request-ID"] == "abc123"


def test_wrong_password_gives_401_in_our_error_shape(client):
    response = client.post("/auth/login", json={"username": "viewer", "password": "wrong"})

    body = response.json()
    assert response.status_code == 401
    assert body["error"] == "unauthorized"
    assert body["message"] == "Wrong username or password"
    assert body["request_id"] == response.headers["X-Request-ID"]


def test_missing_token_gives_401(client):
    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.json()["error"] == "unauthorized"


def test_bad_request_body_gives_422_invalid_request(client):
    response = client.post("/auth/login", json={"username": ""})

    body = response.json()
    assert response.status_code == 422
    assert body["error"] == "invalid_request"
    assert len(body["details"]) == 2


def test_unknown_url_gives_404_in_our_error_shape(client):
    response = client.get("/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"] == "http_error"


def test_too_many_requests_gives_429_with_retry_after(client, viewer_token):
    headers = {"Authorization": f"Bearer {viewer_token}"}
    for _ in range(10):
        assert client.get("/auth/me", headers=headers).status_code == 200

    response = client.get("/auth/me", headers=headers)

    body = response.json()
    assert response.status_code == 429
    assert body["error"] == "rate_limited"
    assert body["retry_after"] == int(response.headers["Retry-After"])


def test_unexpected_crash_gives_safe_500(client):
    @client.app.get("/boom")
    async def boom():
        raise RuntimeError("secret internal detail")

    response = client.get("/boom")

    body = response.json()
    assert response.status_code == 500
    assert body["error"] == "internal_error"
    assert "secret" not in body["message"]
