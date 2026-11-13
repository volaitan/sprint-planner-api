"""Request and response models (Pydantic v2)."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from .models import Role, SprintStatus, StoryStatus


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Auth ----------
class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=72)


class UserOut(ORM):
    id: int
    email: EmailStr
    name: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- Teams ----------
class TeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class MemberOut(BaseModel):
    user: UserOut
    role: Role


class TeamOut(ORM):
    id: int
    name: str


class TeamDetail(TeamOut):
    members: list[MemberOut]


class MemberAdd(BaseModel):
    email: EmailStr
    role: Role = Role.member


# ---------- Sprints ----------
class SprintBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    goal: str = ""
    start_date: date
    end_date: date
    capacity: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def dates_in_order(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class SprintCreate(SprintBase):
    pass


class SprintUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    goal: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    capacity: int | None = Field(default=None, ge=0)


class SprintOut(ORM):
    id: int
    team_id: int
    name: str
    goal: str
    start_date: date
    end_date: date
    capacity: int | None
    status: SprintStatus
    committed_points: int = 0
    completed_points: int = 0


# ---------- Stories ----------
class StoryCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    points: int = Field(default=0, ge=0, le=100)
    assignee_id: int | None = None
    sprint_id: int | None = None


class StoryUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    points: int | None = Field(default=None, ge=0, le=100)
    status: StoryStatus | None = None
    assignee_id: int | None = None
    sprint_id: int | None = None


class StoryOut(ORM):
    id: int
    team_id: int
    sprint_id: int | None
    title: str
    description: str
    points: int
    status: StoryStatus
    assignee_id: int | None
    completed_on: date | None


# ---------- Reports ----------
class BurndownDay(BaseModel):
    date: date
    ideal: float
    remaining: int | None  # None for days that haven't happened yet


class Burndown(BaseModel):
    sprint_id: int
    committed_points: int
    days: list[BurndownDay]


class Velocity(BaseModel):
    sprints: list[dict]
    average: float
    forecast_next: float
