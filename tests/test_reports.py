from datetime import date

from test_sprints_and_stories import add_story


def test_burndown_tracks_completed_points_per_day(client, alice, team, sprint, fake_today):
    h = alice["headers"]
    a = add_story(client, alice, team, title="A", points=5, sprint_id=sprint["id"]).json()
    b = add_story(client, alice, team, title="B", points=3, sprint_id=sprint["id"]).json()
    add_story(client, alice, team, title="C", points=2, sprint_id=sprint["id"])
    client.post(f"/sprints/{sprint['id']}/start", headers=h)

    fake_today.value = date(2026, 1, 6)
    client.patch(f"/stories/{a['id']}", json={"status": "done"}, headers=h)
    fake_today.value = date(2026, 1, 7)
    client.patch(f"/stories/{b['id']}", json={"status": "done"}, headers=h)

    chart = client.get(f"/sprints/{sprint['id']}/burndown", headers=h).json()
    assert chart["committed_points"] == 10
    days = chart["days"]
    assert [d["date"] for d in days] == ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09"]
    assert [d["ideal"] for d in days] == [10.0, 7.5, 5.0, 2.5, 0.0]
    # Future days have no actual value yet
    assert [d["remaining"] for d in days] == [10, 5, 2, None, None]


def test_velocity_and_forecast(client, alice, team, fake_today):
    h = alice["headers"]
    completed_per_sprint = [8, 12, 10, 14]
    for i, points in enumerate(completed_per_sprint, start=1):
        sp = client.post(
            f"/teams/{team['id']}/sprints",
            json={"name": f"Sprint {i}", "start_date": f"2026-0{i}-01", "end_date": f"2026-0{i}-14"},
            headers=h,
        ).json()
        story = add_story(client, alice, team, points=points, sprint_id=sp["id"]).json()
        add_story(client, alice, team, points=2, sprint_id=sp["id"])  # never finished
        client.post(f"/sprints/{sp['id']}/start", headers=h)
        client.patch(f"/stories/{story['id']}", json={"status": "done"}, headers=h)
        client.post(f"/sprints/{sp['id']}/complete", headers=h)

    v = client.get(f"/teams/{team['id']}/velocity", headers=h).json()
    assert [s["completed"] for s in v["sprints"]] == completed_per_sprint
    # Commitment includes the unfinished 2-point story, even though it went back to the backlog
    assert [s["committed"] for s in v["sprints"]] == [p + 2 for p in completed_per_sprint]
    assert v["average"] == 11.0
    assert v["forecast_next"] == 12.0  # average of last three: (12 + 10 + 14) / 3


def test_velocity_empty(client, alice, team):
    v = client.get(f"/teams/{team['id']}/velocity", headers=alice["headers"]).json()
    assert v == {"sprints": [], "average": 0.0, "forecast_next": 0.0}


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}
