"""Typed HTTP projections for the WIRE/98 browser boundary."""

from pydantic import BaseModel, ConfigDict


class Projection(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AccountView(Projection):
    id: str
    handle: str


class SessionView(Projection):
    authenticated: bool
    account: AccountView | None


class PostView(Projection):
    id: int
    author: str
    body: str
    created_at: str
    like_count: int
    liked_by_me: bool
