from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from . import models
from .database import engine
from .db_migrate import ensure_schema
from .socket_manager import manager
from .routers import auth, patient, doctor, reception

models.Base.metadata.create_all(bind=engine)
ensure_schema(engine)

app = FastAPI(title="Smart Hospital Management System")

origins = ["http://localhost:5173", "http://127.0.0.1:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(patient.router)
app.include_router(doctor.router)
app.include_router(reception.router)


@app.get("/")
def read_root():
    return {"message": "Smart Hospital Management API"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # clients can send pings; we ignore payload and keep connection open
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)

