"""
Gas Dynamics Simulator — FastAPI Entry Point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.simulate import router as simulate_router

app = FastAPI(
    title="Gas Dynamics Simulator",
    description="1D Steady-State Gas Dynamics Flow Simulator",
    version="1.0.0",
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(simulate_router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "Gas Dynamics Simulator API is running"}
