"""CPIC RAG Backend — FastAPI application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import query, ingest, phenotype, status

app = FastAPI(
    title="CPIC RAG API",
    description="Pharmacogenomics decision support powered by CPIC guidelines",
    version="1.0.0",
)

# CORS — allow frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(query.router)
app.include_router(ingest.router)
app.include_router(phenotype.router)
app.include_router(status.router)


@app.get("/")
async def root():
    return {"message": "CPIC RAG API is running", "docs": "/docs"}
