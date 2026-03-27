"""Pydantic models for Canvas API responses."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class Course(BaseModel):
    """Canvas course model."""
    id: int
    name: str
    course_code: str
    workflow_state: str = "available"
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    
    class Config:
        extra = "ignore"


class File(BaseModel):
    """Canvas file model."""
    id: int
    display_name: str
    filename: str
    folder_id: Optional[int] = None
    size: int = 0
    content_type: str = Field(alias="content-type", default="application/octet-stream")
    url: str
    updated_at: datetime
    locked: bool = False
    hidden: bool = False
    lock_at: Optional[datetime] = None
    unlock_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    
    class Config:
        populate_by_name = True
        extra = "ignore"  # Ignore extra fields from Canvas API


class Folder(BaseModel):
    """Canvas folder model."""
    id: int
    name: str
    full_name: str
    parent_folder_id: Optional[int] = None
    context_id: int
    files_count: int = 0
    folders_count: int = 0
    
    class Config:
        extra = "ignore"


class Assignment(BaseModel):
    """Canvas assignment model."""
    id: int
    name: str
    description: Optional[str] = None
    due_at: Optional[datetime] = None
    unlock_at: Optional[datetime] = None
    lock_at: Optional[datetime] = None
    points_possible: Optional[float] = None
    submission_types: List[str] = []
    has_submitted_submissions: bool = False
    published: bool = True
    
    class Config:
        extra = "ignore"


class Announcement(BaseModel):
    """Canvas announcement model."""
    id: int
    title: str
    message: Optional[str] = None
    posted_at: Optional[datetime] = None
    author: Optional[dict] = None
    
    class Config:
        extra = "ignore"


class CalendarEvent(BaseModel):
    """Canvas calendar event model."""
    id: int
    title: str
    description: Optional[str] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    all_day: bool = False
    location_name: Optional[str] = None
    workflow_state: str = "active"
    
    class Config:
        extra = "ignore"


class Module(BaseModel):
    """Canvas module model."""
    id: int
    name: str
    position: int
    unlock_at: Optional[datetime] = None
    require_sequential_progress: bool = False
    publish_final_grade: bool = False
    prerequisite_module_ids: List[int] = []
    state: str = "completed"
    completed_at: Optional[datetime] = None
    items_count: int = 0
    items_url: str
    
    class Config:
        extra = "ignore"


class ModuleItem(BaseModel):
    """Canvas module item model."""
    id: int
    module_id: int
    position: int
    title: str
    indent: int = 0
    type: str  # File, Page, Discussion, Assignment, Quiz, SubHeader, ExternalUrl, ExternalTool
    content_id: Optional[int] = None
    html_url: Optional[str] = None
    url: Optional[str] = None
    published: bool = True
    
    class Config:
        extra = "ignore"
