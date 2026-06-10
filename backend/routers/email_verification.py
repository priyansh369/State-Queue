from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from datetime import timedelta

import schemas
from auth_utils import (
    create_email_token,
    verify_email_token,
    get_password_hash,
    EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES,
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES,
)
from database import get_db
from mongo import utcnow
from email_service import send_verification_email, send_password_reset_email

router = APIRouter(prefix="/auth", tags=["email-verification"])


@router.post("/verify-email/{token}")
def verify_email(token: str, db=Depends(get_db)):
    """
    Verify user's email with the token sent to their inbox.
    """
    users_collection = db.users.find({})

    for user in users_collection:
        stored_token_hash = user.get("verification_token")
        if stored_token_hash and verify_email_token(token, stored_token_hash):
            expiry = user.get("verification_token_expiry")
            if expiry and expiry < utcnow():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Verification token has expired",
                )

            db.users.update_one(
                {"id": user["id"]},
                {
                    "$set": {
                        "email_verified": True,
                        "verification_token": None,
                        "verification_token_expiry": None,
                    }
                },
            )
            return {"message": "Email verified successfully. You can now login."}

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid or expired verification token",
    )


@router.post("/resend-verification-email")
def resend_verification_email(request: schemas.EmailRequest, background_tasks: BackgroundTasks, db=Depends(get_db)):
    """
    Resend verification email to user.
    """
    user = db.users.find_one({"email": request.email})

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.get("email_verified", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already verified",
        )

    raw_token, hashed_token = create_email_token("email_verification")
    expiry = utcnow() + timedelta(minutes=EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES)

    db.users.update_one(
        {"id": user["id"]},
        {
            "$set": {
                "verification_token": hashed_token,
                "verification_token_expiry": expiry,
            }
        },
    )

    background_tasks.add_task(send_verification_email, request.email, raw_token)

    return {"message": "Verification email sent. Check your inbox."}


@router.post("/request-password-reset")
def request_password_reset(request: schemas.EmailRequest, background_tasks: BackgroundTasks, db=Depends(get_db)):
    """
    Request a password reset. Sends reset link to user's email.
    """
    user = db.users.find_one({"email": request.email})

    if not user:
        return {"message": "If email exists, password reset link will be sent."}

    raw_token, hashed_token = create_email_token("password_reset")
    expiry = utcnow() + timedelta(minutes=PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)

    db.users.update_one(
        {"id": user["id"]},
        {
            "$set": {
                "password_reset_token": hashed_token,
                "password_reset_token_expiry": expiry,
            }
        },
    )

    background_tasks.add_task(send_password_reset_email, request.email, raw_token)

    return {"message": "If email exists, password reset link will be sent."}


@router.post("/reset-password/{token}")
def reset_password(token: str, request: schemas.PasswordResetRequest, db=Depends(get_db)):
    """
    Reset password using reset token.
    """
    users_collection = db.users.find({})

    for user in users_collection:
        stored_token_hash = user.get("password_reset_token")
        if stored_token_hash and verify_email_token(token, stored_token_hash):
            expiry = user.get("password_reset_token_expiry")
            if expiry and expiry < utcnow():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Reset token has expired",
                )

            new_password_hash = get_password_hash(request.new_password)
            db.users.update_one(
                {"id": user["id"]},
                {
                    "$set": {
                        "password": new_password_hash,
                        "password_reset_token": None,
                        "password_reset_token_expiry": None,
                    }
                },
            )
            return {"message": "Password reset successfully. You can now login with your new password."}

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid or expired reset token",
    )
