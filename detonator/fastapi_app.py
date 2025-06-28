from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Detonator API", version="0.1.0")

# Add CORS middleware to allow requests from Flask frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5000"],  # Flask will run on port 5000
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Detonator API is running"}

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "detonator-api"}

@app.get("/api/items")
async def get_items():
    # Example endpoint - replace with your actual data
    return {
        "items": [
            {"id": 1, "name": "Item 1", "description": "First item"},
            {"id": 2, "name": "Item 2", "description": "Second item"},
            {"id": 3, "name": "Item 3", "description": "Third item"}
        ]
    }

@app.post("/api/items")
async def create_item(item: dict):
    # Example endpoint - replace with your actual logic
    return {"message": "Item created", "item": item}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
