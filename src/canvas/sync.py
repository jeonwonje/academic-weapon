"""Canvas sync orchestrator."""
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Set
from src.config import settings
from src.canvas.client import CanvasClient
from src.canvas.downloader import FileDownloader
from src.canvas.models import Course

logger = logging.getLogger(__name__)


class CanvasSync:
    """Orchestrates syncing Canvas data to local storage."""
    
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or settings.data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.courses_file = self.data_dir / "courses.json"
        self.last_sync_file = self.data_dir / "last_sync.json"
    
    def _save_json(self, file_path: Path, data: any):
        """Save data to JSON file."""
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str, ensure_ascii=False)
    
    def _load_json(self, file_path: Path) -> Optional[dict]:
        """Load data from JSON file."""
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load {file_path}: {e}")
        return None
    
    def _get_course_dir(self, course: Course) -> Path:
        """Get directory path for a course."""
        safe_name = course.course_code.replace("/", "-").replace("\\", "-")
        return self.data_dir / safe_name
    
    async def sync_course(self, client: CanvasClient, course: Course) -> Dict[str, any]:
        """Sync a single course."""
        print(f"\n{'='*60}")
        print(f"Syncing: {course.name} ({course.course_code})")
        print(f"{'='*60}")
        
        course_dir = self._get_course_dir(course)
        course_dir.mkdir(parents=True, exist_ok=True)
        
        stats = {
            "course_id": course.id,
            "course_name": course.name,
            "course_code": course.course_code,
            "synced_at": datetime.now().isoformat(),
        }
        
        try:
            # Fetch folders
            print("Fetching folders...")
            folders = await client.get_folders(course.id)
            print(f"  Found {len(folders)} folders")
            
            # Fetch files
            print("Fetching files...")
            files = await client.get_files(course.id)
            print(f"  Found {len(files)} files")
            
            # Also discover files referenced in module items
            # (some files are only accessible via modules, not the files API)
            print("Checking module items for additional files...")
            file_ids_from_api = {f.id for f in files}
            module_file_count = 0
            try:
                modules = await client.get_modules(course.id)
                for module in modules:
                    try:
                        items = await client.get_module_items(course.id, module.id)
                        for item in items:
                            if item.type == "File" and item.content_id and item.content_id not in file_ids_from_api:
                                file_obj = await client.get_file_by_id(item.content_id)
                                if file_obj:
                                    files.append(file_obj)
                                    file_ids_from_api.add(file_obj.id)
                                    module_file_count += 1
                    except Exception as e:
                        logger.warning(f"  Could not fetch items for module '{module.name}': {e}")
            except Exception as e:
                logger.warning(f"  Could not fetch modules for file discovery: {e}")
            
            if module_file_count > 0:
                print(f"  Found {module_file_count} additional files from module items")
                print(f"  Total files to process: {len(files)}")
            
            # Download files with deduplication
            downloader = FileDownloader(client, course_dir)
            file_stats = await downloader.sync_files(files, folders)
            stats["files"] = file_stats
            
            # Optionally cleanup deleted files
            current_file_ids = {f.id for f in files}
            removed = downloader.cleanup_deleted_files(current_file_ids)
            stats["files"]["removed"] = removed
            
            # Fetch assignments
            print("Fetching assignments...")
            assignments = await client.get_assignments(course.id)
            print(f"  Found {len(assignments)} assignments")
            self._save_json(
                course_dir / "assignments.json",
                [a.model_dump() for a in assignments]
            )
            stats["assignments"] = len(assignments)
            
            # Fetch announcements
            print("Fetching announcements...")
            announcements = await client.get_announcements(course.id)
            print(f"  Found {len(announcements)} announcements")
            self._save_json(
                course_dir / "announcements.json",
                [a.model_dump() for a in announcements]
            )
            stats["announcements"] = len(announcements)
            
            # Fetch calendar events
            print("Fetching calendar events...")
            events = await client.get_calendar_events(course.id)
            print(f"  Found {len(events)} events")
            self._save_json(
                course_dir / "calendar_events.json",
                [e.model_dump() for e in events]
            )
            stats["calendar_events"] = len(events)
            
            # Save modules (already fetched above during file discovery)
            print(f"  Saving {len(modules)} modules")
            self._save_json(
                course_dir / "modules.json",
                [m.model_dump() for m in modules]
            )
            stats["modules"] = len(modules)
            
            print(f"\n[OK] Successfully synced {course.course_code}")
            print(f"   Files: {file_stats['downloaded']} downloaded, {file_stats['skipped']} unchanged, {removed} removed")
            print(f"   Assignments: {len(assignments)}, Announcements: {len(announcements)}, Events: {len(events)}")
            
            stats["success"] = True
            
        except Exception as e:
            print(f"\n[ERROR] Error syncing {course.course_code}: {e}")
            stats["success"] = False
            stats["error"] = str(e)
        
        return stats
    
    async def fetch_courses(self) -> list:
        """Fetch courses from Canvas and save them. Returns raw course list."""
        async with CanvasClient() as client:
            courses = await client.get_courses()
            self._save_json(
                self.courses_file,
                [c.model_dump() for c in courses]
            )
            return courses

    async def sync_all(self, selected_course_ids: Optional[List[int]] = None) -> Dict[str, any]:
        """Sync all courses (or only selected ones)."""
        print(f"\n{'#'*60}")
        print(f"# Canvas Auto-Sync")
        print(f"# Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'#'*60}")
        
        results = {
            "started_at": datetime.now().isoformat(),
            "courses": [],
        }
        
        async with CanvasClient() as client:
            # Fetch courses
            print("\nFetching course list...")
            courses = await client.get_courses()
            print(f"Found {len(courses)} active courses")
            
            # Filter to selected courses if specified
            if selected_course_ids:
                courses = [c for c in courses if c.id in selected_course_ids]
                print(f"Syncing {len(courses)} selected courses")
            
            # Save course list
            self._save_json(
                self.courses_file,
                [c.model_dump() for c in courses]
            )
            
            # Sync each course
            for course in courses:
                course_stats = await self.sync_course(client, course)
                results["courses"].append(course_stats)
        
        # Save sync results
        results["completed_at"] = datetime.now().isoformat()
        results["success_count"] = sum(1 for c in results["courses"] if c.get("success"))
        results["failed_count"] = sum(1 for c in results["courses"] if not c.get("success"))
        
        self._save_json(self.last_sync_file, results)
        
        print(f"\n{'#'*60}")
        print(f"# Sync Complete!")
        print(f"# Successful: {results['success_count']}, Failed: {results['failed_count']}")
        print(f"# Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'#'*60}\n")
        
        return results
