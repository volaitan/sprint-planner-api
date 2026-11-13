from conftest import register


def test_register_login_me(client):
    user = register(client, "Victor@Example.com", "Victor")
    me = client.get("/auth/me", headers=user["headers"]).json()
    assert me["email"] == "victor@example.com"  # stored lower-case


def test_duplicate_email_and_bad_login(client, alice):
    res = client.post("/auth/register", json={"email": "alice@example.com", "name": "A", "password": "password123"})
    assert res.status_code == 409
    res = client.post("/auth/login", data={"username": "alice@example.com", "password": "wrong-password"})
    assert res.status_code == 401


def test_password_rules(client):
    res = client.post("/auth/register", json={"email": "x@example.com", "name": "X", "password": "short"})
    assert res.status_code == 422


def test_protected_routes_need_valid_token(client):
    assert client.get("/teams").status_code == 401
    assert client.get("/teams", headers={"Authorization": "Bearer nonsense"}).status_code == 401


def test_create_team_makes_creator_owner(client, alice, team):
    assert team["members"][0]["role"] == "owner"
    assert [t["name"] for t in client.get("/teams", headers=alice["headers"]).json()] == ["Web Team"]


def test_non_members_cannot_see_team(client, bob, team):
    assert client.get(f"/teams/{team['id']}", headers=bob["headers"]).status_code == 404
    assert client.get(f"/teams/{team['id']}/stories", headers=bob["headers"]).status_code == 404


def test_owner_adds_and_removes_members(client, alice, bob, team):
    tid = team["id"]
    res = client.post(f"/teams/{tid}/members", json={"email": "bob@example.com"}, headers=alice["headers"])
    assert res.status_code == 201
    assert {m["user"]["name"] for m in res.json()["members"]} == {"Alice", "Bob"}

    # Bob is a member now, but not an owner
    assert client.get(f"/teams/{tid}", headers=bob["headers"]).status_code == 200
    res = client.post(f"/teams/{tid}/members", json={"email": "alice@example.com"}, headers=bob["headers"])
    assert res.status_code == 403

    assert client.post(f"/teams/{tid}/members", json={"email": "bob@example.com"}, headers=alice["headers"]).status_code == 409
    assert client.post(f"/teams/{tid}/members", json={"email": "nobody@example.com"}, headers=alice["headers"]).status_code == 404

    assert client.delete(f"/teams/{tid}/members/{bob['id']}", headers=alice["headers"]).status_code == 204
    assert client.get(f"/teams/{tid}", headers=bob["headers"]).status_code == 404


def test_last_owner_cannot_leave(client, alice, team):
    res = client.delete(f"/teams/{team['id']}/members/{alice['id']}", headers=alice["headers"])
    assert res.status_code == 409
