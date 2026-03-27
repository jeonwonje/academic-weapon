"""
Example: How to use the Canvas sync programmatically in your own scripts
"""
import asyncio
from src.canvas.sync import CanvasSync


async def example_sync_all_courses():
    """Example: Sync all courses."""
    syncer = CanvasSync()
    results = await syncer.sync_all()
    
    print(f"Synced {results['success_count']} courses successfully")
    for course in results['courses']:
        if course['success']:
            print(f"  ✓ {course['course_code']}: {course['files']['downloaded']} files downloaded")


async def example_sync_specific_courses():
    """Example: Sync only specific courses by ID."""
    syncer = CanvasSync()
    
    # Replace with your actual course IDs
    selected_course_ids = [12345, 67890]
    
    results = await syncer.sync_all(selected_course_ids=selected_course_ids)
    print(f"Synced {results['success_count']} selected courses")


async def example_custom_client():
    """Example: Use the Canvas client directly."""
    from src.canvas.client import CanvasClient
    
    async with CanvasClient() as client:
        # Get all courses
        courses = await client.get_courses()
        print(f"Found {len(courses)} courses:")
        
        for course in courses:
            print(f"  - {course.name} ({course.course_code})")
            
            # Get assignments for this course
            assignments = await client.get_assignments(course.id)
            print(f"    {len(assignments)} assignments")
            
            # Get upcoming deadlines
            upcoming = [a for a in assignments if a.due_at and a.due_at.date() >= datetime.now().date()]
            if upcoming:
                print(f"    Upcoming deadlines:")
                for assignment in sorted(upcoming, key=lambda x: x.due_at):
                    print(f"      - {assignment.name}: {assignment.due_at.strftime('%Y-%m-%d')}")


async def example_download_specific_files():
    """Example: Download specific files only."""
    from src.canvas.client import CanvasClient
    from src.canvas.downloader import FileDownloader
    from pathlib import Path
    
    async with CanvasClient() as client:
        course_id = 12345  # Replace with your course ID
        
        # Get files
        files = await client.get_files(course_id)
        folders = await client.get_folders(course_id)
        
        # Filter for specific file types (e.g., PDFs only)
        pdf_files = [f for f in files if f.filename.endswith('.pdf')]
        
        # Download
        course_dir = Path("data/custom_course")
        downloader = FileDownloader(client, course_dir)
        results = await downloader.sync_files(pdf_files, folders)
        
        print(f"Downloaded {results['downloaded']} PDF files")


if __name__ == "__main__":
    from datetime import datetime
    
    # Run one of the examples
    asyncio.run(example_sync_all_courses())
    # asyncio.run(example_sync_specific_courses())
    # asyncio.run(example_custom_client())
    # asyncio.run(example_download_specific_files())
