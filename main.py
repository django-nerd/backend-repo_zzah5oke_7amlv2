import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from bson import ObjectId

from database import db, create_document, get_documents
import schemas as schema_models

# ----------------------------
# App & CORS
# ----------------------------
app = FastAPI(title="StronX API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------
# Security & Auth Config
# ----------------------------
SECRET_KEY = os.getenv("JWT_SECRET", "dev-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# ----------------------------
# Helpers
# ----------------------------

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


def serialize_doc(doc: dict) -> dict:
    if not doc:
        return doc
    d = doc.copy()
    _id = d.get("_id")
    if isinstance(_id, ObjectId):
        d["id"] = str(_id)
        del d["_id"]
    return d


# ----------------------------
# Schemas for auth endpoints
# ----------------------------
class RegisterRequest(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    role: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


# ----------------------------
# Basic endpoints
# ----------------------------
@app.get("/")
def read_root():
    return {"message": "StronX API is running"}


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


# ----------------------------
# Auth routes
# ----------------------------
@app.post("/auth/register", response_model=TokenResponse)
def register(payload: RegisterRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    existing = db["authuser"].find_one({"email": payload.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user_doc = {
        "full_name": payload.full_name,
        "email": str(payload.email).lower(),
        "role": payload.role,
        "hashed_password": get_password_hash(payload.password),
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    res = db["authuser"].insert_one(user_doc)
    user_doc["_id"] = res.inserted_id

    token = create_access_token({"sub": str(user_doc["_id"]), "email": user_doc["email"], "role": user_doc["role"]})
    safe_user = serialize_doc(user_doc)
    del safe_user["hashed_password"]
    return {"access_token": token, "user": safe_user}


@app.post("/auth/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    email = form_data.username.lower()
    user = db["authuser"].find_one({"email": email})
    if not user or not verify_password(form_data.password, user.get("hashed_password", "")):
        raise HTTPException(status_code=400, detail="Incorrect email or password")

    token = create_access_token({"sub": str(user["_id"]), "email": user["email"], "role": user.get("role", "")})
    safe_user = serialize_doc(user)
    if "hashed_password" in safe_user:
        del safe_user["hashed_password"]
    return {"access_token": token, "user": safe_user}


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    credentials_exception = HTTPException(status_code=401, detail="Could not validate credentials")
    try:
        payload = decode_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except Exception:
        raise credentials_exception
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    user = db["authuser"].find_one({"_id": ObjectId(user_id)})
    if user is None:
        raise credentials_exception
    safe_user = serialize_doc(user)
    if "hashed_password" in safe_user:
        del safe_user["hashed_password"]
    return safe_user


@app.get("/auth/me")
async def read_users_me(current_user: dict = Depends(get_current_user)):
    return current_user


# ----------------------------
# CRUD: Projects, Tasks, RFIs, Approvals, Documents (Create + List)
# ----------------------------

class CreateProject(BaseModel):
    title: str
    code: str
    description: Optional[str] = None


@app.post("/api/projects")
async def create_project(payload: CreateProject, user: dict = Depends(get_current_user)):
    data = schema_models.Project(title=payload.title, code=payload.code, description=payload.description)
    new_id = create_document("project", data)
    return {"id": new_id}


@app.get("/api/projects")
async def list_projects(limit: int = 20):
    docs = get_documents("project", limit=limit)
    return [serialize_doc(d) for d in docs]


class CreateTask(BaseModel):
    project_code: str
    title: str
    description: Optional[str] = None


@app.post("/api/tasks")
async def create_task(payload: CreateTask, user: dict = Depends(get_current_user)):
    data = schema_models.Task(project_code=payload.project_code, title=payload.title, description=payload.description)
    new_id = create_document("task", data)
    return {"id": new_id}


@app.get("/api/tasks")
async def list_tasks(project_code: Optional[str] = None, limit: int = 50):
    filt = {"project_code": project_code} if project_code else None
    docs = get_documents("task", filter_dict=filt, limit=limit)
    return [serialize_doc(d) for d in docs]


class CreateRFI(BaseModel):
    project_code: str
    subject: str
    question: str


@app.post("/api/rfis")
async def create_rfi(payload: CreateRFI, user: dict = Depends(get_current_user)):
    data = schema_models.RFI(project_code=payload.project_code, subject=payload.subject, question=payload.question)
    new_id = create_document("rfi", data)
    return {"id": new_id}


@app.get("/api/rfis")
async def list_rfis(project_code: Optional[str] = None, limit: int = 50):
    filt = {"project_code": project_code} if project_code else None
    docs = get_documents("rfi", filter_dict=filt, limit=limit)
    return [serialize_doc(d) for d in docs]


class CreateApproval(BaseModel):
    related_type: str
    related_id: str


@app.post("/api/approvals")
async def create_approval(payload: CreateApproval, user: dict = Depends(get_current_user)):
    data = schema_models.Approval(related_type=payload.related_type, related_id=payload.related_id)
    new_id = create_document("approval", data)
    return {"id": new_id}


@app.get("/api/approvals")
async def list_approvals(limit: int = 50):
    docs = get_documents("approval", limit=limit)
    return [serialize_doc(d) for d in docs]


class CreateDocument(BaseModel):
    project_code: str
    title: str
    doc_type: str = "other"


@app.post("/api/documents")
async def create_document_api(payload: CreateDocument, user: dict = Depends(get_current_user)):
    data = schema_models.Document(project_code=payload.project_code, title=payload.title, doc_type=payload.doc_type)
    new_id = create_document("document", data)
    return {"id": new_id}


@app.get("/api/documents")
async def list_documents(project_code: Optional[str] = None, limit: int = 50):
    filt = {"project_code": project_code} if project_code else None
    docs = get_documents("document", filter_dict=filt, limit=limit)
    return [serialize_doc(d) for d in docs]


# ----------------------------
# Schema export for frontend tooling
# ----------------------------
@app.get("/schema")
def get_schema_index():
    """Expose the Pydantic schema definitions to the frontend tooling/viewer."""
    try:
        exported = {}
        for name, obj in schema_models.__dict__.items():
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
