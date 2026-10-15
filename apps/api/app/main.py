from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import core

app = FastAPI(title="Scholarly Pattern Explorer API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(core.router, prefix="/api/v1")
