"""
Main entry point for the FastAPI application.

This module initializes the FastAPI app, sets up lifespan events for database
initialization, and defines the core API endpoints.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from .database.connection import create_db_and_tables

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    An asynchronous context manager to handle application startup and shutdown events.

    This lifespan event is triggered once when the server starts. It is the
    ideal place to initialize resources like database connections and tables.
    The 'yield' statement passes control back to the application, which runs
    until it receives a shutdown signal.
    """
    print("Application startup: Initializing database...")
    create_db_and_tables()
    print("Database initialization complete.")
    
    yield
    
    # Code below yield runs on application shutdown.
    print("Application shutdown.")

# Initialize the main FastAPI application instance.
app = FastAPI(
    title="MTG AI Deck Builder API",
    description="API for ingesting MTG collections, managing card data, and building decks.",
    version="0.1.0",
    lifespan=lifespan,
)

@app.get("/health", tags=["Status"])
def health_check():
    """
    A simple health check endpoint.

    Returns a 200 OK response if the API server is running, which can be used
    for automated health checks by monitoring services.
    """
    return {"status": "ok"}