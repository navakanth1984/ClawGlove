import os
import sys

def check_upgrade_path():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    releases_dir = os.path.join(base_dir, "releases")
    
    print(f"[*] Checking platform upgrade path at: {releases_dir}")
    
    expected_versions = [
        "v1.0",
        "v1.1",
        "v1.2",
        "v1.3",
        "v1.4",
        "v1.5",
        "v1.6",
        "v1.7",
        "v1.8",
        "v1.9",
        "v2.0"
    ]
    missing_notes = []
    
    for version in expected_versions:
        notes_file = f"{version}.md"
        notes_path = os.path.join(releases_dir, notes_file)
        if not os.path.exists(notes_path):
            missing_notes.append(notes_file)
            print(f"[ERROR] Missing release documentation: {notes_file}")
        else:
            print(f"[SUCCESS] Release notes exist: {notes_file}")
            
    if missing_notes:
        print(f"\n[ERROR] Upgrade path check FAILED! Missing release history logs.")
        sys.exit(1)
    else:
        print("\n[SUCCESS] Upgrade path check PASSED! All release note migrations are traceable.")
        sys.exit(0)

if __name__ == "__main__":
    check_upgrade_path()
