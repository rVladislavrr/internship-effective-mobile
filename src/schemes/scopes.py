from pydantic import BaseModel, UUID4


class ScopeRead(BaseModel):
    id: int
    name: str
    description: str | None

    model_config = {"from_attributes": True}


class ScopeGroupRead(BaseModel):
    id: int
    name: str
    description: str | None

    model_config = {"from_attributes": True}


class ScopeGroupWithScopes(BaseModel):
    id: int
    name: str
    description: str | None
    scopes: list[ScopeRead] = []

    model_config = {"from_attributes": True}


class AssignScopeRequest(BaseModel):
    user_id: UUID4
    scope_id: int


class RevokeScopeRequest(BaseModel):
    user_id: UUID4
    scope_id: int


class AssignGroupRequest(BaseModel):
    user_id: UUID4
    group_id: int


class RevokeGroupRequest(BaseModel):
    user_id: UUID4
    group_id: int