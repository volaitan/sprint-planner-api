from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import reports
from ..database import get_db
from ..deps import get_membership, require_owner
from ..models import Membership, Role, Sprint, Team, User
from ..schemas import MemberAdd, MemberOut, TeamCreate, TeamDetail, TeamOut, UserOut, Velocity
from ..security import get_current_user

router = APIRouter(prefix="/teams", tags=["teams"])


def team_detail(team: Team) -> TeamDetail:
    return TeamDetail(
        id=team.id,
        name=team.name,
        members=[MemberOut(user=UserOut.model_validate(m.user), role=m.role) for m in team.memberships],
    )


@router.post("", response_model=TeamDetail, status_code=status.HTTP_201_CREATED)
def create_team(body: TeamCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    team = Team(name=body.name.strip())
    team.memberships.append(Membership(user=user, role=Role.owner))
    db.add(team)
    db.commit()
    db.refresh(team)
    return team_detail(team)


@router.get("", response_model=list[TeamOut])
def my_teams(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Team).join(Membership).where(Membership.user_id == user.id).order_by(Team.id)).all()


@router.get("/{team_id}", response_model=TeamDetail)
def get_team(team_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return team_detail(get_membership(db, team_id, user).team)


@router.post("/{team_id}/members", response_model=TeamDetail, status_code=status.HTTP_201_CREATED)
def add_member(team_id: int, body: MemberAdd, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    team = require_owner(db, team_id, user).team
    new_user = db.scalar(select(User).where(User.email == body.email.lower()))
    if new_user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No user with that email; ask them to register first")
    if any(m.user_id == new_user.id for m in team.memberships):
        raise HTTPException(status.HTTP_409_CONFLICT, "User is already a member")
    team.memberships.append(Membership(user=new_user, role=body.role))
    db.commit()
    db.refresh(team)
    return team_detail(team)


@router.delete("/{team_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(team_id: int, user_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_owner(db, team_id, user)
    membership = db.scalar(select(Membership).where(Membership.team_id == team_id, Membership.user_id == user_id))
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    if membership.role == Role.owner:
        owners = db.scalar(
            select(func.count()).select_from(Membership).where(Membership.team_id == team_id, Membership.role == Role.owner)
        )
        if owners == 1:
            raise HTTPException(status.HTTP_409_CONFLICT, "A team must keep at least one owner")
    db.delete(membership)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{team_id}/velocity", response_model=Velocity)
def team_velocity(team_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_membership(db, team_id, user)
    sprints = db.scalars(select(Sprint).where(Sprint.team_id == team_id)).all()
    return reports.velocity(list(sprints))

