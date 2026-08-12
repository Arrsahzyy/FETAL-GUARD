from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.dependencies import get_current_user
from core.auth_rate_limit import assert_login_allowed, clear_failed_logins, record_failed_login
from core.refresh_tokens import (
    issue_refresh_token,
    revoke_all_refresh_tokens,
    rotate_refresh_token,
    revoke_refresh_token,
)
from core.tenancy import resolve_patient_registration_organization
from db.database import get_db
from models.patient import Patient
from models.user import User
from schemas.user import (
    LogoutRequest,
    PasswordChange,
    PatientRegistration,
    RefreshTokenRequest,
    Token,
    UserCreate,
    UserResponse,
    UserRole,
)
from core.security import get_password_hash, verify_password, create_access_token
from core.config import settings
from core.db_context import set_postgresql_request_context

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    if user_in.role != UserRole.patient:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff accounts must be provisioned by an administrator",
        )
    resolve_patient_registration_organization(db)

    user = db.query(User).filter(User.email == user_in.email).first()
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "PATIENT_REGISTRATION_REJECTED",
                "message": "Patient registration could not be completed",
            },
        )
    user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        role=user_in.role.value,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "PATIENT_REGISTRATION_REJECTED",
                "message": "Patient registration could not be completed",
            },
        )
    db.refresh(user)
    return user


@router.post("/register/patient", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_patient_account(registration: PatientRegistration, db: Session = Depends(get_db)):
    if registration.role != UserRole.patient:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only patient self-registration is allowed",
        )
    if db.query(User).filter(User.email == registration.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "PATIENT_REGISTRATION_REJECTED",
                "message": "Patient registration could not be completed",
            },
        )

    user = User(
        email=registration.email,
        hashed_password=get_password_hash(registration.password),
        role=UserRole.patient.value,
    )
    db.add(user)
    try:
        db.flush()
        set_postgresql_request_context(db, user_id=user.id)
        patient_values = registration.profile.model_dump()
        organization = resolve_patient_registration_organization(db)
        db.add(Patient(user_id=user.id, organization_id=organization.id, **patient_values))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "PATIENT_REGISTRATION_REJECTED",
                "message": "Patient registration could not be completed",
            },
        )
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login_access_token(
    request: Request,
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    normalized_email, client_key = assert_login_allowed(db, email=form_data.username, request=request)
    user = db.query(User).filter(User.email == normalized_email).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        record_failed_login(db, email=normalized_email, client_key=client_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is inactive",
        )
    clear_failed_logins(db, email=normalized_email, client_key=client_key)
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.id,
        role=user.role,
        expires_delta=access_token_expires,
        auth_version=user.auth_version or 0,
    )
    refresh_token = issue_refresh_token(db, user, request)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.post("/refresh", response_model=Token)
def refresh_access_token(
    refresh_in: RefreshTokenRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    user, refresh_token = rotate_refresh_token(db, refresh_in.refresh_token, request)
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.id,
        role=user.role,
        expires_delta=access_token_expires,
        auth_version=user.auth_version or 0,
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.post("/logout")
def logout(
    logout_in: LogoutRequest,
    db: Session = Depends(get_db),
):
    revoke_refresh_token(db, logout_in.refresh_token)
    return {"detail": "Logged out"}


@router.get("/me", response_model=UserResponse)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/password", response_model=UserResponse)
def change_password(
    password_in: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(password_in.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    if password_in.current_password == password_in.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from the current password",
        )

    current_user.hashed_password = get_password_hash(password_in.new_password)
    current_user.must_reset_password = False
    current_user.auth_version = (current_user.auth_version or 0) + 1
    current_user.password_changed_at = datetime.now(timezone.utc)
    revoke_all_refresh_tokens(db, current_user.id, commit=False)
    db.commit()
    db.refresh(current_user)
    return current_user
