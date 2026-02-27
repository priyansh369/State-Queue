from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth_utils import (
    create_access_token,
    get_password_hash,
    is_bcrypt_hash,
    verify_password,
)
from ..database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=schemas.UserOut)
def register_user(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == user_in.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    if user_in.role not in [
        models.UserRoleEnum.PATIENT,
        models.UserRoleEnum.DOCTOR,
        models.UserRoleEnum.RECEPTIONIST,
    ]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role",
        )
    user = models.User(
        name=user_in.name,
        email=user_in.email,
        password=get_password_hash(user_in.password),
        role=user_in.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=schemas.Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not is_bcrypt_hash(user.password):
        user.password = get_password_hash(form_data.password)
        db.add(user)
        db.commit()
    access_token = create_access_token({"sub": user.id, "role": user.role})
    return schemas.Token(
        access_token=access_token,
        user_id=user.id,
        role=user.role,
        name=user.name,
    )


@router.get("/doctors", response_model=list[schemas.DoctorOut])
def list_doctors(db: Session = Depends(get_db)):
    doctors = (
        db.query(models.User)
        .filter(models.User.role == models.UserRoleEnum.DOCTOR)
        .order_by(models.User.name.asc())
        .all()
    )
    return doctors

