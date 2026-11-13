from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import clock
from ..database import get_db
from ..deps import get_membership, get_story
from ..models import Membership, Sprint, SprintStatus, Story, StoryStatus, User
from ..schemas import StoryCreate, StoryOut, StoryUpdate
from ..security import get_current_user

router = APIRouter(tags=["stories"])


def check_assignee(db: Session, team_id: int, assignee_id: int | None) -> None:
    if assignee_id is None:
        return
    if db.scalar(select(Membership).where(Membership.team_id == team_id, Membership.user_id == assignee_id)) is None:
        raise HTTPException(422, "Assignee must be a member of the team")


def check_sprint(db: Session, team_id: int, sprint_id: int | None, extra_points: int, force: bool) -> None:
    """Story must go into an open sprint of the same team, and not blow the sprint's capacity."""
    if sprint_id is None:
        return
    sprint = db.get(Sprint, sprint_id)
    if sprint is None or sprint.team_id != team_id:
        raise HTTPException(422, "Sprint not found in this team")
    if sprint.status == SprintStatus.completed:
        raise HTTPException(status.HTTP_409_CONFLICT, "Cannot add stories to a completed sprint")
    if sprint.capacity is not None and not force:
        committed = sum(s.points for s in sprint.stories)
        if committed + extra_points > sprint.capacity:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Over capacity: sprint has {committed}/{sprint.capacity} points committed; "
                f"adding {extra_points} would exceed it. Use ?force=true to override.",
            )


@router.post("/teams/{team_id}/stories", response_model=StoryOut, status_code=status.HTTP_201_CREATED)
def create_story(
    team_id: int,
    body: StoryCreate,
    force: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_membership(db, team_id, user)
    check_assignee(db, team_id, body.assignee_id)
    check_sprint(db, team_id, body.sprint_id, body.points, force)
    story = Story(team_id=team_id, **body.model_dump())
    db.add(story)
    db.commit()
    db.refresh(story)
    return story


@router.get("/teams/{team_id}/stories", response_model=list[StoryOut])
def list_stories(
    team_id: int,
    sprint_id: int | None = None,
    backlog: bool = Query(False, description="Only stories not in any sprint"),
    status_filter: StoryStatus | None = Query(None, alias="status"),
    assignee_id: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_membership(db, team_id, user)
    q = select(Story).where(Story.team_id == team_id)
    if backlog:
        q = q.where(Story.sprint_id.is_(None))
    elif sprint_id is not None:
        q = q.where(Story.sprint_id == sprint_id)
    if status_filter is not None:
        q = q.where(Story.status == status_filter)
    if assignee_id is not None:
        q = q.where(Story.assignee_id == assignee_id)
    return db.scalars(q.order_by(Story.id)).all()


@router.get("/stories/{story_id}", response_model=StoryOut)
def read_story(story_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_story(db, story_id, user)


@router.patch("/stories/{story_id}", response_model=StoryOut)
def update_story(
    story_id: int,
    body: StoryUpdate,
    force: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    story = get_story(db, story_id, user)
    changes = body.model_dump(exclude_unset=True)

    if "assignee_id" in changes:
        check_assignee(db, story.team_id, changes["assignee_id"])
    if "sprint_id" in changes and changes["sprint_id"] != story.sprint_id:
        check_sprint(db, story.team_id, changes["sprint_id"], changes.get("points", story.points), force)
    elif "points" in changes and story.sprint_id is not None:
        check_sprint(db, story.team_id, story.sprint_id, changes["points"] - story.points, force)

    new_status = changes.get("status")
    if new_status is not None and new_status != story.status:
        # Track when work is finished so the burndown chart is accurate.
        story.completed_on = clock.today() if new_status == StoryStatus.done else None

    for key, value in changes.items():
        setattr(story, key, value)
    db.commit()
    db.refresh(story)
    return story


@router.delete("/stories/{story_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_story(story_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    story = get_story(db, story_id, user)
    db.delete(story)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
