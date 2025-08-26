from contextlib import asynccontextmanager
from fastapi import FastAPI

# Import our database creation function
from .database.connection import create_db_and_tables

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Application startup...")
    create_db_and_tables()
    
    yield
    
    print("Application shutdown...")


# Create the main FastAPI app instance, passing in lifespan manager
app = FastAPI(
    title="MTG AI Deck Builder API",
    description="API for ingesting MTG collections and building decks.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["Status"])
def health_check():
    """Check if the API is running."""
    return {"status": "ok"}