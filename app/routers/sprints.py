from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import clock, reports
from ..database import get_db
from ..deps import get_membership, get_sprint
from ..models import Sprint, SprintStatus, StoryStatus, User
from ..schemas import Burndown, SprintCreate, SprintOut, SprintUpdate
from ..security import get_current_user

router = APIRouter(tags=["sprints"])


def sprint_out(sprint: Sprint) -> SprintOut:
    committed, completed = reports.sprint_points(sprint)
    out = SprintOut.model_validate(sprint)
    out.committed_points, out.completed_points = committed, completed
    return out


@router.post("/teams/{team_id}/sprints", response_model=SprintOut, status_code=status.HTTP_201_CREATED)
def create_sprint(team_id: int, body: SprintCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_membership(db, team_id, user)
    sprint = Sprint(team_id=team_id, **body.model_dump())
    db.add(sprint)
    db.commit()
    db.refresh(sprint)
    return sprint_out(sprint)


@router.get("/teams/{team_id}/sprints", response_model=list[SprintOut])
def list_sprints(team_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_membership(db, team_id, user)
    sprints = db.scalars(select(Sprint).where(Sprint.team_id == team_id).order_by(Sprint.start_date)).all()
    return [sprint_out(s) for s in sprints]


@router.get("/sprints/{sprint_id}", response_model=SprintOut)
def read_sprint(sprint_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return sprint_out(get_sprint(db, sprint_id, user))


@router.patch("/sprints/{sprint_id}", response_model=SprintOut)
def update_sprint(sprint_id: int, body: SprintUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sprint = get_sprint(db, sprint_id, user)
    if sprint.status == SprintStatus.completed:
        raise HTTPException(status.HTTP_409_CONFLICT, "Completed sprints cannot be edited")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(sprint, key, value)
    if sprint.end_date < sprint.start_date:
        raise HTTPException(422, "end_date must be on or after start_date")
    db.commit()
    return sprint_out(sprint)


@router.post("/sprints/{sprint_id}/start", response_model=SprintOut)
def start_sprint(sprint_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sprint = get_sprint(db, sprint_id, user)
    if sprint.status != SprintStatus.planned:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Sprint is already {sprint.status.value}")
    active = db.scalar(select(Sprint).where(Sprint.team_id == sprint.team_id, Sprint.status == SprintStatus.active))
    if active is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Finish '{active.name}' before starting another sprint")
    if not sprint.stories:
        raise HTTPException(status.HTTP_409_CONFLICT, "Add stories to the sprint before starting it")
    sprint.status = SprintStatus.active
    db.commit()
    return sprint_out(sprint)


@router.post("/sprints/{sprint_id}/complete", response_model=SprintOut)
def complete_sprint(sprint_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Close the sprint. Unfinished stories go back to the backlog, as in Scrum."""
    sprint = get_sprint(db, sprint_id, user)
    if sprint.status != SprintStatus.active:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only an active sprint can be completed")
    # Record the commitment before unfinished work moves out, so velocity stays accurate.
    sprint.committed_at_close = sum(s.points for s in sprint.stories)
    for story in sprint.stories:
        if story.status != StoryStatus.done:
            story.sprint_id = None
            story.status = StoryStatus.todo
    sprint.status = SprintStatus.completed
    db.commit()
    db.refresh(sprint)
    return sprint_out(sprint)


@router.get("/sprints/{sprint_id}/burndown", response_model=Burndown)
def sprint_burndown(sprint_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sprint = get_sprint(db, sprint_id, user)
    committed, _ = reports.sprint_points(sprint)
    return Burndown(sprint_id=sprint.id, committed_points=committed, days=reports.burndown(sprint, clock.today()))
