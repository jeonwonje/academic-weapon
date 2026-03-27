"""File downloader with deduplication support."""
import json
import hashlib
from pathlib import Path
from typing import Dict, Set, Optional
from datetime import datetime
from urllib.parse import unquote_plus
import aiofiles
import asyncio
from tqdm.asyncio import tqdm

from src.canvas.client import CanvasClient
from src.canvas.models import File, Folder


class FileDownloader:
    """Downloads files from Canvas with intelligent deduplication."""
    
    def __init__(self, client: CanvasClient, course_dir: Path):
        self.client = client
        self.course_dir = course_dir
        self.files_dir = course_dir / "files"
        self.meta_file = course_dir / ".sync_meta.json"
        self.meta: Dict[str, dict] = self._load_meta()
        
    def _load_meta(self) -> Dict[str, dict]:
        """Load sync metadata from file."""
        if self.meta_file.exists():
            try:
                with open(self.meta_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load sync meta: {e}")
        return {}
    
    def _save_meta(self):
        """Save sync metadata to file."""
        self.meta_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.meta_file, "w", encoding="utf-8") as f:
            json.dump(self.meta, f, indent=2, default=str)
    
    def _needs_download(self, file: File) -> bool:
        """Check if file needs to be downloaded based on metadata."""
        file_key = str(file.id)
        
        if file_key not in self.meta:
            return True
        
        meta = self.meta[file_key]
        
        # Check if file was updated
        if file.updated_at.isoformat() != meta.get("updated_at"):
            return True
        
        # Check if file content was modified (Canvas tracks this separately)
        if file.modified_at:
            stored_modified = meta.get("modified_at")
            if stored_modified is None or file.modified_at.isoformat() != stored_modified:
                return True
        
        # Check if file size changed
        if file.size != meta.get("size"):
            return True
        
        # Check if local file exists
        local_path = self.files_dir / meta.get("path", "")
        if not local_path.exists():
            return True
        
        # Check if local file size matches
        if local_path.stat().st_size != file.size:
            return True
        
        return False
    
    def _get_safe_filename(self, name: str) -> str:
        """Convert filename to safe filesystem name."""
        # Decode URL-encoded characters (+ -> space, %20 -> space, etc.)
        name = unquote_plus(name)
        # Replace invalid filesystem characters
        invalid_chars = '<>:"|?*\\'
        for char in invalid_chars:
            name = name.replace(char, "_")
        return name.strip()
    
    def _get_folder_path(self, folder_id: Optional[int], folders: Dict[int, Folder]) -> Path:
        """Recursively build folder path."""
        if folder_id is None or folder_id not in folders:
            return Path("")
        
        folder = folders[folder_id]
        parent_path = self._get_folder_path(folder.parent_folder_id, folders)
        safe_name = self._get_safe_filename(folder.name)
        return parent_path / safe_name
    
    async def download_file(self, file: File, relative_path: Path, max_retries: int = 3) -> Optional[Path]:
        """Download a single file with retry logic."""
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                # Download file content
                content = await self.client.download_file(file.url)
                
                # Save to disk
                local_path = self.files_dir / relative_path
                local_path.parent.mkdir(parents=True, exist_ok=True)
                
                async with aiofiles.open(local_path, "wb") as f:
                    await f.write(content)
                
                # Update metadata
                self.meta[str(file.id)] = {
                    "id": file.id,
                    "name": file.display_name,
                    "path": str(relative_path),
                    "size": file.size,
                    "updated_at": file.updated_at.isoformat(),
                    "modified_at": file.modified_at.isoformat() if file.modified_at else None,
                    "downloaded_at": datetime.now().isoformat(),
                }
                
                return local_path
            
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    wait = 2 ** attempt  # exponential backoff: 2s, 4s, 8s
                    print(f"  Retry {attempt}/{max_retries} for {file.display_name} (waiting {wait}s): {e}")
                    await asyncio.sleep(wait)
                else:
                    print(f"Error downloading {file.display_name} after {max_retries} attempts: {last_error}")
        
        return None
    
    async def sync_files(self, files: list[File], folders: list[Folder]) -> Dict[str, any]:
        """Sync all files with deduplication."""
        # Build folder lookup
        folder_map = {folder.id: folder for folder in folders}
        
        # Filter files that need downloading
        to_download = []
        skipped = 0
        
        locked_count = 0
        for file in files:
            # Don't skip locked/hidden files - they may still be accessible.
            # Canvas sets locked=True for files with date restrictions even
            # when the file is currently within its access window.
            if file.locked or file.hidden:
                locked_count += 1
            
            if self._needs_download(file):
                to_download.append(file)
            else:
                skipped += 1
        
        if locked_count > 0:
            print(f"  ({locked_count} files have lock/hidden flags - will attempt download anyway)")
        
        print(f"Found {len(files)} files: {len(to_download)} to download, {skipped} unchanged")
        
        # Download files
        downloaded = []
        failed = []
        
        if to_download:
            print(f"Downloading {len(to_download)} files...")
            
            # Create download tasks
            tasks = []
            for file in to_download:
                # Build relative path
                folder_path = self._get_folder_path(file.folder_id, folder_map)
                # Prefer display_name (clean) over filename (URL-encoded)
                safe_filename = self._get_safe_filename(file.display_name)
                relative_path = folder_path / safe_filename
                
                tasks.append(self.download_file(file, relative_path))
            
            # Execute downloads with progress bar
            results = await tqdm.gather(*tasks, desc="Downloading")
            
            for file, result in zip(to_download, results):
                if result:
                    downloaded.append(file.display_name)
                else:
                    failed.append(file.display_name)
        
        # Save metadata
        self._save_meta()
        
        return {
            "total": len(files),
            "downloaded": len(downloaded),
            "skipped": skipped,
            "failed": len(failed),
            "failed_files": failed,
        }
    
    def cleanup_deleted_files(self, current_file_ids: Set[int]) -> int:
        """Remove local files that no longer exist on Canvas."""
        removed = 0
        meta_keys_to_remove = []
        
        for file_id_str, meta in self.meta.items():
            file_id = int(file_id_str)
            if file_id not in current_file_ids:
                local_path = self.files_dir / meta.get("path", "")
                if local_path.exists():
                    try:
                        local_path.unlink()
                        removed += 1
                    except Exception as e:
                        print(f"Warning: Could not delete {local_path}: {e}")
                meta_keys_to_remove.append(file_id_str)
        
        # Remove from metadata
        for key in meta_keys_to_remove:
            del self.meta[key]
        
        if removed > 0:
            self._save_meta()
            print(f"Removed {removed} deleted files")
        
        return removed
