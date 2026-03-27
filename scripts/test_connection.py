"""Test Canvas API connection and credentials."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.canvas.client import CanvasClient
from src.config import settings


async def test_connection():
    """Test Canvas API connection and display basic info."""
    print("🔍 Testing Canvas API Connection...")
    print("=" * 60)
    print(f"Canvas URL: {settings.canvas_api_url}")
    print(f"API Token: {'*' * 20}{settings.canvas_api_token[-4:]}")
    print("=" * 60)
    print()
    
    try:
        async with CanvasClient() as client:
            print("✓ Connecting to Canvas API...")
            
            # Fetch courses
            courses = await client.get_courses()
            print(f"✓ Successfully authenticated!")
            print(f"✓ Found {len(courses)} active courses")
            print()
            
            if courses:
                print("Your Courses:")
                print("-" * 60)
                for i, course in enumerate(courses, 1):
                    print(f"{i:2}. {course.course_code:15} - {course.name}")
                print("-" * 60)
                print()
                
                # Test fetching data from first course
                test_course = courses[0]
                print(f"Testing data fetch for: {test_course.course_code}")
                print("-" * 60)
                
                files = await client.get_files(test_course.id)
                print(f"  ✓ Files: {len(files)}")
                
                assignments = await client.get_assignments(test_course.id)
                print(f"  ✓ Assignments: {len(assignments)}")
                
                announcements = await client.get_announcements(test_course.id)
                print(f"  ✓ Announcements: {len(announcements)}")
                
                folders = await client.get_folders(test_course.id)
                print(f"  ✓ Folders: {len(folders)}")
                
                print()
                print("=" * 60)
                print("✅ All tests passed! Your setup is working correctly.")
                print("=" * 60)
                print()
                print("Next step: Run the full sync with:")
                print("  python scripts/sync_canvas.py")
                print()
            else:
                print("⚠️  No active courses found.")
                print("   This might be normal if you're not enrolled in any courses.")
        
        return 0
        
    except Exception as e:
        print()
        print("=" * 60)
        print("❌ Connection test failed!")
        print("=" * 60)
        print(f"Error: {e}")
        print()
        print("Common issues:")
        print("  1. Invalid API token - Generate a new one from Canvas Settings")
        print("  2. Wrong Canvas URL - Check CANVAS_API_URL in .env")
        print("  3. Network issues - Check your internet connection")
        print("  4. Token expired - Generate a new token")
        print()
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(test_connection())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
