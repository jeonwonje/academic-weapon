"""Async Canvas API client."""
import httpx
from typing import List, Optional, Dict, Any
from src.config import settings
from src.canvas.models import (
    Course, File, Folder, Assignment, 
    Announcement, CalendarEvent, Module, ModuleItem
)
import logging

logger = logging.getLogger(__name__)


class CanvasClient:
    """Async client for Canvas LMS API."""
    
    def __init__(self, api_token: Optional[str] = None, api_url: Optional[str] = None):
        self.api_token = api_token or settings.canvas_api_token
        self.api_url = (api_url or settings.canvas_api_url).rstrip("/")
        self.base_url = f"{self.api_url}/api/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }
        self.client = httpx.AsyncClient(headers=self.headers, timeout=60.0)
        # Separate client for file downloads with longer timeout
        self.download_client = httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=30.0))
    
    async def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> List[Dict]:
        """Make a GET request to Canvas API with pagination support."""
        results = []
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        if params is None:
            params = {}
        params["per_page"] = 100  # Max items per page
        
        while url:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            if isinstance(data, list):
                results.extend(data)
            else:
                results.append(data)
            
            # Check for pagination links
            link_header = response.headers.get("Link", "")
            url = None
            if link_header:
                links = self._parse_link_header(link_header)
                url = links.get("next")
            
            # Only use params on first request
            params = None
        
        return results
    
    @staticmethod
    def _parse_link_header(header: str) -> Dict[str, str]:
        """Parse Link header for pagination."""
        links = {}
        for link in header.split(","):
            parts = link.split(";")
            if len(parts) == 2:
                url = parts[0].strip()[1:-1]  # Remove < >
                rel = parts[1].strip().split("=")[1].strip('"')
                links[rel] = url
        return links
    
    async def get_courses(self, enrollment_state: str = "active") -> List[Course]:
        """Get all courses for the current user."""
        data = await self._get("courses", {
            "enrollment_state": enrollment_state,
            "include[]": ["total_scores", "current_grading_period_scores"]
        })
        return [Course(**item) for item in data]
    
    async def get_folders(self, course_id: int) -> List[Folder]:
        """Get all folders in a course."""
        data = await self._get(f"courses/{course_id}/folders")
        return [Folder(**item) for item in data]
    
    async def get_files(self, course_id: int) -> List[File]:
        """Get all files in a course."""
        data = await self._get(f"courses/{course_id}/files", {
            "sort": "updated_at",
            "order": "desc",
        })
        files = []
        for item in data:
            try:
                files.append(File(**item))
            except Exception as e:
                logger.warning(f"Could not parse file {item.get('id')} ({item.get('display_name', 'unknown')}): {e}")
                # Try again with more lenient parsing - strip unknown fields
                try:
                    known_fields = {f.name for f in File.model_fields.values()} | {f.alias for f in File.model_fields.values() if f.alias}
                    known_keys = {'id', 'display_name', 'filename', 'folder_id', 'size', 
                                  'content-type', 'content_type', 'url', 'updated_at',
                                  'locked', 'hidden', 'lock_at', 'unlock_at', 'modified_at'}
                    cleaned = {k: v for k, v in item.items() if k in known_keys}
                    files.append(File(**cleaned))
                    logger.info(f"  Recovered file {item.get('id')} with lenient parsing")
                except Exception as e2:
                    logger.error(f"  SKIPPED file {item.get('id')} ({item.get('display_name', 'unknown')}): {e2}")
                    logger.error(f"  Raw API fields: {list(item.keys())}")
        return files
    
    async def get_folder_files(self, folder_id: int) -> List[File]:
        """Get all files in a specific folder."""
        data = await self._get(f"folders/{folder_id}/files")
        return [File(**item) for item in data]
    
    async def get_assignments(self, course_id: int) -> List[Assignment]:
        """Get all assignments in a course."""
        data = await self._get(f"courses/{course_id}/assignments")
        return [Assignment(**item) for item in data]
    
    async def get_announcements(self, course_id: int) -> List[Announcement]:
        """Get all announcements in a course."""
        data = await self._get(f"courses/{course_id}/discussion_topics", {
            "only_announcements": True
        })
        return [Announcement(**item) for item in data]
    
    async def get_calendar_events(self, course_id: int) -> List[CalendarEvent]:
        """Get all calendar events for a course."""
        data = await self._get("calendar_events", {
            "context_codes[]": f"course_{course_id}",
            "all_events": True
        })
        return [CalendarEvent(**item) for item in data]
    
    async def get_modules(self, course_id: int) -> List[Module]:
        """Get all modules in a course."""
        data = await self._get(f"courses/{course_id}/modules", {
            "include[]": ["items"]
        })
        return [Module(**item) for item in data]
    
    async def get_module_items(self, course_id: int, module_id: int) -> List[ModuleItem]:
        """Get all items in a module."""
        data = await self._get(f"courses/{course_id}/modules/{module_id}/items")
        return [ModuleItem(**item) for item in data]
    
    async def download_file(self, url: str) -> bytes:
        """Download a file from Canvas using the dedicated download client."""
        response = await self.download_client.get(
            url, 
            follow_redirects=True,
            headers={"Authorization": f"Bearer {self.api_token}"}
        )
        response.raise_for_status()
        return response.content
    
    async def get_file_by_id(self, file_id: int) -> Optional[File]:
        """Get a single file by ID (useful for module-linked files)."""
        try:
            data = await self._get(f"files/{file_id}")
            if data:
                item = data[0] if isinstance(data, list) else data
                return File(**item)
        except Exception as e:
            logger.warning(f"Could not fetch file {file_id}: {e}")
        return None
    
    async def close(self):
        """Close the HTTP clients."""
        await self.client.aclose()
        await self.download_client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
