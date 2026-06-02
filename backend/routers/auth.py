from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

import models, schemas
from auth_utils import (
    create_access_token,
    get_password_hash,
    is_bcrypt_hash,
    verify_password,
)
from database import get_db
from mongo import next_id, safe_insert_one, utcnow

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=schemas.UserOut)
def register_user(user_in: schemas.UserCreate, db=Depends(get_db)):
    existing = db.users.find_one({"email": user_in.email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    if user_in.role not in [
        models.UserRoleEnum.PATIENT,
        models.UserRoleEnum.DOCTOR,
        models.UserRoleEnum.RECEPTIONIST,
        models.UserRoleEnum.ADMIN,
    ]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role",
        )
    user = {
        "id": next_id("users"),
        "name": user_in.name,
        "email": user_in.email,
        "password": get_password_hash(user_in.password),
        "role": user_in.role,
        "is_available": True,
        "created_at": utcnow(),
    }
    try:
        safe_insert_one(db.users, user)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    return {"id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"]}


@router.post("/login", response_model=schemas.Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db=Depends(get_db)
):
    user = db.users.find_one({"email": form_data.username})
    if not user or not verify_password(form_data.password, user.get("password", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not is_bcrypt_hash(user.get("password", "")):
        new_hash = get_password_hash(form_data.password)
        db.users.update_one({"id": user["id"]}, {"$set": {"password": new_hash}})
    access_token = create_access_token({"sub": user["id"], "role": user["role"]})
    return schemas.Token(
        access_token=access_token,
        user_id=user["id"],
        role=user["role"],
        name=user["name"],
    )


@router.get("/doctors", response_model=list[schemas.DoctorOut])
def list_doctors(db=Depends(get_db)):
    doctors = list(
        db.users.find(
            {"role": models.UserRoleEnum.DOCTOR, "is_available": True},
            {"_id": 0, "id": 1, "name": 1, "is_available": 1},
        ).sort("name", 1)
    )
    return doctors
