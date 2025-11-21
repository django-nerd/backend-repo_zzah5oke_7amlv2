"""
Database Schemas for Construction Lifecycle Platform

Each Pydantic model maps to a MongoDB collection using the lowercased
class name as the collection name.

Core design principles:
- Strong typing with Pydantic for validation
- Versioned documents where applicable (documents, drawings)
- Embedded audit trails for critical ops
- Role-based access control via Role and Permission models
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime

# ----------------------------
# Security & Users
# ----------------------------
class Permission(BaseModel):
    code: str = Field(..., description="Unique permission code, e.g., projects.view, tenders.create")
    description: Optional[str] = None

class Role(BaseModel):
    name: Literal[
        "contractor",
        "site_engineer",
        "project_manager",
        "client",
        "owner",
        "labourer",
        "auditor",
        "admin",
    ]
    permissions: List[str] = Field(default_factory=list, description="List of permission codes")

class User(BaseModel):
    full_name: str
    email: EmailStr
    phone: Optional[str] = None
    role: str = Field(..., description="Role name that maps to Role collection")
    company: Optional[str] = None
    is_active: bool = True

# ----------------------------
# Project & Lifecycle
# ----------------------------
class Project(BaseModel):
    title: str
    code: str = Field(..., description="Unique project code")
    description: Optional[str] = None
    owner_org: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: Literal["planning", "tender", "execution", "handover", "closed"] = "planning"
    budget: Optional[float] = None
    currency: str = "USD"
    stakeholders: List[str] = Field(default_factory=list, description="User IDs involved")

class Tender(BaseModel):
    project_code: str
    tender_no: str
    title: str
    scope: Optional[str] = None
    issue_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    documents: List[str] = Field(default_factory=list, description="IDs of document records")
    status: Literal["draft", "published", "closed", "awarded"] = "draft"

class Bid(BaseModel):
    tender_no: str
    bidder_org: str
    amount: float
    currency: str = "USD"
    submitted_by: Optional[str] = None
    submitted_at: Optional[datetime] = None
    attachments: List[str] = Field(default_factory=list)
    status: Literal["draft", "submitted", "under_review", "won", "lost"] = "draft"

class Contract(BaseModel):
    project_code: str
    contract_no: str
    parties: List[str] = Field(..., description="Organizations involved")
    value: float
    currency: str = "USD"
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: Literal["draft", "active", "suspended", "completed", "terminated"] = "draft"
    documents: List[str] = Field(default_factory=list)

# ----------------------------
# Documentation & Compliance
# ----------------------------
class DocumentVersion(BaseModel):
    version: str
    file_id: str = Field(..., description="Pointer to storage provider object id")
    checksum: Optional[str] = None
    uploaded_by: Optional[str] = None
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    change_note: Optional[str] = None

class Document(BaseModel):
    project_code: str
    title: str
    doc_type: Literal[
        "contract",
        "drawing",
        "spec",
        "inspection",
        "material_test",
        "permit",
        "handover",
        "rfi",
        "safety",
        "other",
    ] = "other"
    tags: List[str] = Field(default_factory=list)
    current_version: str = "v1"
    versions: List[DocumentVersion] = Field(default_factory=list)
    is_confidential: bool = False

class Signature(BaseModel):
    user_id: str
    signed_at: datetime = Field(default_factory=datetime.utcnow)
    signature_type: Literal["digital", "aadhaar", "wet_copy_scanned"] = "digital"
    comment: Optional[str] = None

class Approval(BaseModel):
    related_type: Literal["tender", "bid", "contract", "document", "task", "rfi"]
    related_id: str
    status: Literal["pending", "approved", "rejected"] = "pending"
    requested_by: Optional[str] = None
    approvers: List[str] = Field(default_factory=list)
    signatures: List[Signature] = Field(default_factory=list)
    audit_log_ids: List[str] = Field(default_factory=list)

class AuditLog(BaseModel):
    project_code: Optional[str] = None
    actor_id: Optional[str] = None
    action: str
    entity_type: str
    entity_id: str
    meta: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)

# ----------------------------
# Execution: Quality, Safety, Tasks
# ----------------------------
class Task(BaseModel):
    project_code: str
    title: str
    description: Optional[str] = None
    assigned_to: Optional[str] = None
    start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    status: Literal["todo", "in_progress", "blocked", "done", "verified"] = "todo"
    priority: Literal["low", "medium", "high", "critical"] = "medium"

class ChecklistItem(BaseModel):
    text: str
    required: bool = True
    status: Literal["pending", "ok", "fail"] = "pending"
    note: Optional[str] = None
    photo_ids: List[str] = Field(default_factory=list)

class QualityChecklist(BaseModel):
    project_code: str
    name: str
    items: List[ChecklistItem] = Field(default_factory=list)
    created_by: Optional[str] = None
    location: Optional[str] = None
    geo: Optional[dict] = None

class Snag(BaseModel):
    project_code: str
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    geo: Optional[dict] = None
    photo_ids: List[str] = Field(default_factory=list)
    status: Literal["open", "in_progress", "resolved", "verified"] = "open"
    raised_by: Optional[str] = None
    assigned_to: Optional[str] = None

class SafetyIncident(BaseModel):
    project_code: str
    category: Literal["near_miss", "injury", "hazard", "other"] = "other"
    description: str
    severity: Literal["low", "medium", "high", "critical"] = "low"
    occurred_at: datetime = Field(default_factory=datetime.utcnow)
    location: Optional[str] = None
    geo: Optional[dict] = None
    photo_ids: List[str] = Field(default_factory=list)
    reported_by: Optional[str] = None
    status: Literal["reported", "investigating", "resolved"] = "reported"

# ----------------------------
# RFIs and Communication
# ----------------------------
class RFIMessage(BaseModel):
    author_id: str
    message: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    attachments: List[str] = Field(default_factory=list)

class RFI(BaseModel):
    project_code: str
    subject: str
    question: str
    raised_by: Optional[str] = None
    messages: List[RFIMessage] = Field(default_factory=list)
    status: Literal["open", "answered", "closed"] = "open"

# ----------------------------
# Labour & Productivity
# ----------------------------
class Attendance(BaseModel):
    project_code: str
    user_id: str
    date: datetime = Field(default_factory=datetime.utcnow)
    check_in: Optional[datetime] = None
    check_out: Optional[datetime] = None
    geo_in: Optional[dict] = None
    geo_out: Optional[dict] = None

class ProductivityLog(BaseModel):
    project_code: str
    task_id: Optional[str] = None
    user_id: Optional[str] = None
    quantity: float = 0
    unit: str = "units"
    logged_at: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = None

class TrainingModule(BaseModel):
    title: str
    description: Optional[str] = None
    duration_minutes: int = 15
    tags: List[str] = Field(default_factory=list)

class Certification(BaseModel):
    user_id: str
    module_id: str
    completed_at: datetime = Field(default_factory=datetime.utcnow)
    score: Optional[float] = None

# ----------------------------
# Integrations
# ----------------------------
class IntegrationConfig(BaseModel):
    name: Literal[
        "erp",
        "eprocurement",
        "payment_gateway",
        "hrms",
        "bim",
        "object_storage",
    ]
    provider: str
    config: dict = Field(default_factory=dict)
    is_enabled: bool = True

# ----------------------------
# Notifications & Automation
# ----------------------------
class NotificationRule(BaseModel):
    name: str
    event: str = Field(..., description="Event code, e.g., workflow.approval.pending")
    recipients_roles: List[str] = Field(default_factory=list)
    recipients_users: List[str] = Field(default_factory=list)
    channels: List[Literal["email", "sms", "push", "webhook"]] = ["email"]
    escalates_after_hours: Optional[int] = None

class Notification(BaseModel):
    event: str
    project_code: Optional[str] = None
    to_user_id: Optional[str] = None
    to_role: Optional[str] = None
    channel: Literal["email", "sms", "push", "webhook"] = "email"
    payload: dict = Field(default_factory=dict)
    sent_at: Optional[datetime] = None

# Note: The Flames database viewer will automatically:
# 1. Read these schemas from GET /schema endpoint
# 2. Use them for document validation when creating/editing
# 3. Handle all database operations (CRUD) directly
# 4. You don't need to create any database endpoints!
