import os
import logging

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from db_migrate import ensure_schema
from mongo import ping_database
from websocket_manager import manager
from routers import auth, patient, doctor, reception, tokens

logger = logging.getLogger(__name__)

app = FastAPI(title="Smart Hospital Management System")
startup_state = {
    "db_ready": False,
    "db_error": None,
}

cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173, http://localhost:5175, http://localhost:5174 ,http://127.0.0.1:5173")
origins = [origin.strip() for origin in cors_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(patient.router)
app.include_router(doctor.router)
app.include_router(reception.router)
app.include_router(tokens.router)


@app.on_event("startup")
def initialize_database():
    try:
        ensure_schema()
        startup_state["db_ready"] = True
        startup_state["db_error"] = None
    except Exception as exc:
        startup_state["db_ready"] = False
        startup_state["db_error"] = str(exc)
        logger.exception("Database initialization failed")


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": str(exc.detail),
                "code": exc.status_code,
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "message": "Validation failed",
                "code": 422,
                "details": exc.errors(),
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, __: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": "Internal server error",
                "code": 500,
            }
        },
    )


@app.get("/")
def read_root():
    return {"message": "Smart Hospital Management API"}


@app.get("/health/db")
def database_health():
    try:
        health = ping_database()
        startup_state["db_ready"] = True
        startup_state["db_error"] = None
        return health
    except Exception as exc:
        startup_state["db_ready"] = False
        startup_state["db_error"] = str(exc)
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "database": os.getenv("MONGODB_DB", "statq"),
                "detail": str(exc),
            },
        )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # clients can send pings; we ignore payload and keep connection open
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
