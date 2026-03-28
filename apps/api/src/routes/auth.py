from uuid import UUID
from pydantic import BaseModel, EmailStr
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.auth import hash_password, verify_password, create_access_token, get_current_user, TokenData
from ..models.user import User

router = APIRouter()


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str
    company: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    token: str
    user: dict


class UserResponse(BaseModel):
    id: UUID
    email: str
    name: str
    company: str | None


@router.post("/register", response_model=AuthResponse)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # Check if user exists
    result = await db.execute(select(User).where(User.email == req.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=req.email,
        password_hash=hash_password(req.password),
        name=req.name,
        company=req.company,
    )
    db.add(user)
    await db.flush()

    token = create_access_token(user.id, user.email)
    return AuthResponse(
        token=token,
        user={"id": str(user.id), "email": user.email, "name": user.name, "company": user.company},
    )


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(user.id, user.email)
    return AuthResponse(
        token=token,
        user={"id": str(user.id), "email": user.email, "name": user.name, "company": user.company},
    )


@router.get("/me", response_model=UserResponse)
async def me(current_user: TokenData = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == current_user.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(id=user.id, email=user.email, name=user.name, company=user.company)
