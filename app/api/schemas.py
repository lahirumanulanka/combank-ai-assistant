from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=100)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    name: str


class MeResponse(BaseModel):
    username: str
    name: str
    role: str
    access_levels: list[str]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    thread_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,64}$")


class ResumeRequest(BaseModel):
    thread_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    approved: bool
