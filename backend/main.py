from fastapi import FastAPI

app = FastAPI(
    title="MTG AI Deck Builder API",
    description="API for ingesting MTG collections and building decks.",
    version="0.1.0",
)

@app.get("/health", tags=["Status"])
def health_check():
    """Check if the API is running."""
    return {"status": "ok"}
