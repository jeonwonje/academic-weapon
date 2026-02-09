"""File downloader with deduplication via .sync_meta.json manifests."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.canvas.client import CanvasClient
from src.canvas.models import CanvasFile, Folder, FileSyncRecord

logger = logging.getLogger(__name__)


class FileDownloader:
    """Downloads Canvas course files to a local directory, skipping unchanged files."""

    def __init__(self, client: CanvasClient, course_dir: Path) -> None:
        self._client = client
        self._course_dir = course_dir
        self._files_dir = course_dir / "files"
        self._files_dir.mkdir(parents=True, exist_ok=True)
        self._meta_path = course_dir / ".sync_meta.json"
        self._meta = self._load_meta()

    # ── Metadata persistence ────────────────────────────────────────────

    def _load_meta(self) -> dict[int, FileSyncRecord]:
        """Load the sync manifest from disk."""
        if not self._meta_path.exists():
            return {}
        try:
            raw = json.loads(self._meta_path.read_text())
            return {
                int(k): FileSyncRecord.model_validate(v) for k, v in raw.items()
            }
        except Exception as exc:
            logger.warning("Corrupt sync manifest, starting fresh: %s", exc)
            return {}

    def _save_meta(self) -> None:
        """Persist the sync manifest to disk."""
        data = {
            str(k): v.model_dump() for k, v in self._meta.items()
        }
        self._meta_path.write_text(json.dumps(data, indent=2, default=str))

    # ── Folder tree reconstruction ──────────────────────────────────────

    @staticmethod
    def _build_folder_map(folders: list[Folder]) -> dict[int, str]:
        """Build a mapping of folder_id → relative path string."""
        folder_map: dict[int, str] = {}
        by_id = {f.id: f for f in folders}

        def resolve(fid: int) -> str:
            if fid in folder_map:
                return folder_map[fid]
            folder = by_id.get(fid)
            if folder is None:
                folder_map[fid] = ""
                return ""
            if folder.parent_folder_id is None or folder.parent_folder_id not in by_id:
                # Root-level folder: use just the name
                path = folder.name
            else:
                parent_path = resolve(folder.parent_folder_id)
                path = f"{parent_path}/{folder.name}" if parent_path else folder.name
            folder_map[fid] = path
            return path

        for f in folders:
            resolve(f.id)
        return folder_map

    # ── Core sync logic ─────────────────────────────────────────────────

    def _needs_download(self, cf: CanvasFile) -> bool:
        """Return True if the remote file is new or updated."""
        record = self._meta.get(cf.id)
        if record is None:
            return True
        remote_ts = cf.updated_at.isoformat() if cf.updated_at else ""
        if record.updated_at != remote_ts:
            return True
        if record.size != cf.size:
            return True
        # Also check the file still exists on disk
        if not Path(record.local_path).exists():
            return True
        return False

    async def sync_files(
        self,
        files: list[CanvasFile],
        folders: list[Folder],
    ) -> dict[str, list[str]]:
        """Download new/updated files. Returns a summary dict.

        Returns:
            {"downloaded": [...], "skipped": [...], "failed": [...]}
        """
        folder_map = self._build_folder_map(folders)
        result: dict[str, list[str]] = {
            "downloaded": [],
            "skipped": [],
            "failed": [],
        }

        for cf in files:
            if cf.locked or cf.hidden:
                continue

            if not self._needs_download(cf):
                result["skipped"].append(cf.display_name)
                continue

            # Determine local path
            folder_path = folder_map.get(cf.folder_id or 0, "")
            # Sanitise folder_path segments
            if folder_path:
                safe_folder = Path(*[
                    self._sanitise_name(seg) for seg in folder_path.split("/") if seg
                ])
            else:
                safe_folder = Path(".")

            dest_dir = self._files_dir / safe_folder
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / self._sanitise_name(cf.display_name or cf.filename)

            try:
                await self._client.download_file(cf.url, str(dest))
                self._meta[cf.id] = FileSyncRecord(
                    file_id=cf.id,
                    display_name=cf.display_name,
                    updated_at=cf.updated_at.isoformat() if cf.updated_at else "",
                    size=cf.size,
                    local_path=str(dest),
                    content_type=cf.content_type,
                )
                result["downloaded"].append(cf.display_name)
                logger.info("Downloaded: %s → %s", cf.display_name, dest)
            except Exception as exc:
                result["failed"].append(cf.display_name)
                logger.error("Failed to download %s: %s", cf.display_name, exc)

        self._save_meta()
        return result

    @staticmethod
    def _sanitise_name(name: str) -> str:
        """Make a string safe for use as a filename."""
        return "".join(
            c if c.isalnum() or c in (".", "-", "_", " ") else "_" for c in name
        ).strip() or "unnamed"
