import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict

from database import db, create_document, get_documents

app = FastAPI(title="Construction Lifecycle Platform API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Construction Lifecycle Platform API is running"}

@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}

@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"

            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response

# Generic document creation endpoint for quick prototyping
class GenericDoc(BaseModel):
    collection: str
    data: Dict[str, Any]

@app.post("/api/create")
def api_create(doc: GenericDoc):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        inserted_id = create_document(doc.collection, doc.data)
        return {"id": inserted_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/schema")
def get_schema_index():
    """Expose the Pydantic schema definitions to the frontend tooling/viewer."""
    try:
        import schemas as schema_module
        exported = {}
        for name, obj in schema_module.__dict__.items():
            try:
                if isinstance(obj, type) and issubclass(obj, BaseModel) and name not in {"BaseModel"}:
                    exported[name] = obj.model_json_schema()
            except Exception:
                continue
        return exported
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Schema export failed: {e}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
