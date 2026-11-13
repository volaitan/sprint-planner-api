def add_story(client, user, team, **fields):
    body = {"title": "Story", "points": 3, **fields}
    params = {"force": "true"} if fields.pop("force", False) else None
    return client.post(f"/teams/{team['id']}/stories", json=body, headers=user["headers"], params=params)


def test_sprint_dates_validated(client, alice, team):
    res = client.post(
        f"/teams/{team['id']}/sprints",
        json={"name": "Bad", "start_date": "2026-02-10", "end_date": "2026-02-01"},
        headers=alice["headers"],
    )
    assert res.status_code == 422


def test_backlog_and_sprint_filters(client, alice, team, sprint):
    add_story(client, alice, team, title="In backlog")
    add_story(client, alice, team, title="In sprint", sprint_id=sprint["id"])
    h = alice["headers"]
    backlog = client.get(f"/teams/{team['id']}/stories", params={"backlog": True}, headers=h).json()
    in_sprint = client.get(f"/teams/{team['id']}/stories", params={"sprint_id": sprint["id"]}, headers=h).json()
    assert [s["title"] for s in backlog] == ["In backlog"]
    assert [s["title"] for s in in_sprint] == ["In sprint"]
    assert client.get(f"/sprints/{sprint['id']}", headers=h).json()["committed_points"] == 3


def test_capacity_is_enforced_unless_forced(client, alice, team, sprint):
    assert add_story(client, alice, team, points=13, sprint_id=sprint["id"]).status_code == 201
    over = add_story(client, alice, team, points=8, sprint_id=sprint["id"])
    assert over.status_code == 409
    assert "capacity" in over.json()["detail"].lower()
    assert add_story(client, alice, team, points=8, sprint_id=sprint["id"], force=True).status_code == 201

    # Raising points on a story already in the sprint is also checked
    story = add_story(client, alice, team, points=0, sprint_id=sprint["id"], force=True).json()
    res = client.patch(f"/stories/{story['id']}", json={"points": 5}, headers=alice["headers"])
    assert res.status_code == 409


def test_assignee_must_be_team_member(client, alice, bob, team):
    assert add_story(client, alice, team, assignee_id=bob["id"]).status_code == 422
    assert add_story(client, alice, team, assignee_id=alice["id"]).status_code == 201


def test_story_from_other_team_is_hidden(client, alice, bob, team):
    story = add_story(client, alice, team).json()
    assert client.get(f"/stories/{story['id']}", headers=bob["headers"]).status_code == 404
    assert client.patch(f"/stories/{story['id']}", json={"title": "x"}, headers=bob["headers"]).status_code == 404


def test_only_one_active_sprint_and_must_have_stories(client, alice, team, sprint):
    h = alice["headers"]
    assert client.post(f"/sprints/{sprint['id']}/start", headers=h).status_code == 409  # empty sprint
    add_story(client, alice, team, sprint_id=sprint["id"])
    assert client.post(f"/sprints/{sprint['id']}/start", headers=h).json()["status"] == "active"

    s2 = client.post(
        f"/teams/{team['id']}/sprints",
        json={"name": "Sprint 2", "start_date": "2026-01-12", "end_date": "2026-01-16"},
        headers=h,
    ).json()
    add_story(client, alice, team, sprint_id=s2["id"])
    res = client.post(f"/sprints/{s2['id']}/start", headers=h)
    assert res.status_code == 409
    assert "Sprint 1" in res.json()["detail"]


def test_completing_sprint_returns_unfinished_work_to_backlog(client, alice, team, sprint, fake_today):
    h = alice["headers"]
    done = add_story(client, alice, team, title="Done", points=5, sprint_id=sprint["id"]).json()
    add_story(client, alice, team, title="Not done", points=3, sprint_id=sprint["id"])
    client.post(f"/sprints/{sprint['id']}/start", headers=h)
    client.patch(f"/stories/{done['id']}", json={"status": "done"}, headers=h)

    res = client.post(f"/sprints/{sprint['id']}/complete", headers=h).json()
    assert res["status"] == "completed"
    assert res["committed_points"] == 8
    assert res["completed_points"] == 5

    backlog = client.get(f"/teams/{team['id']}/stories", params={"backlog": True}, headers=h).json()
    assert [s["title"] for s in backlog] == ["Not done"]
    assert backlog[0]["status"] == "todo"

    assert client.patch(f"/sprints/{sprint['id']}", json={"name": "x"}, headers=h).status_code == 409
    assert add_story(client, alice, team, sprint_id=sprint["id"]).status_code == 409


def test_reopening_a_story_clears_completion_date(client, alice, team, fake_today):
    story = add_story(client, alice, team).json()
    h = alice["headers"]
    done = client.patch(f"/stories/{story['id']}", json={"status": "done"}, headers=h).json()
    assert done["completed_on"] == "2026-01-05"
    reopened = client.patch(f"/stories/{story['id']}", json={"status": "in_progress"}, headers=h).json()
    assert reopened["completed_on"] is None


def test_delete_story(client, alice, team):
    story = add_story(client, alice, team).json()
    assert client.delete(f"/stories/{story['id']}", headers=alice["headers"]).status_code == 204
    assert client.get(f"/stories/{story['id']}", headers=alice["headers"]).status_code == 404
