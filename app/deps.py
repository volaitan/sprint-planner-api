"""Access-control helpers: every team resource is visible only to that team's members."""
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Membership, Role, Sprint, Story, Team, User


def get_membership(db: Session, team_id: int, user: User) -> Membership:
    team = db.get(Team, team_id)
    membership = db.scalar(select(Membership).where(Membership.team_id == team_id, Membership.user_id == user.id))
    # Return 404 (not 403) for teams you don't belong to, so team ids can't be probed.
    if team is None or membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")
    return membership


def require_owner(db: Session, team_id: int, user: User) -> Membership:
    m = get_membership(db, team_id, user)
    if m.role != Role.owner:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only team owners can do this")
    return m


def get_sprint(db: Session, sprint_id: int, user: User) -> Sprint:
    sprint = db.get(Sprint, sprint_id)
    if sprint is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sprint not found")
    get_membership(db, sprint.team_id, user)
    return sprint


def get_story(db: Session, story_id: int, user: User) -> Story:
    story = db.get(Story, story_id)
    if story is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Story not found")
    get_membership(db, story.team_id, user)
    return story
