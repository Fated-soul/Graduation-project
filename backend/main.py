from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import agent, animals, camera, control_commands, devices, public_data, stimulation, system, telemetry, vision, vital_signs
from backend.config import APP_DESCRIPTION, APP_NAME, APP_VERSION, CORS_ORIGINS
from backend.database.init_db import init_database


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_database()
    yield


app = FastAPI(
    title=APP_NAME,
    description=APP_DESCRIPTION,
    version=APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def declare_json_utf8(request, call_next):
    """Keep Windows PowerShell 5.1 from decoding UTF-8 JSON as Latin-1."""
    response = await call_next(request)
    content_type = response.headers.get("content-type", "")
    if (
        content_type.lower().startswith("application/json")
        and "charset=" not in content_type.lower()
    ):
        response.headers["content-type"] = "application/json; charset=utf-8"
    return response


app.include_router(system.router)
app.include_router(animals.router)
app.include_router(camera.router)
app.include_router(devices.router)
app.include_router(telemetry.router)
app.include_router(vital_signs.router)
app.include_router(vision.router)
app.include_router(stimulation.router)
app.include_router(control_commands.router)
app.include_router(agent.router)
app.include_router(public_data.router)
