import os
import sys
import yaml

def verify_structure():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    manifest_path = os.path.join(base_dir, "manifest.yaml")
    
    if not os.path.exists(manifest_path):
        print(f"[ERROR] manifest.yaml not found at {manifest_path}!")
        sys.exit(1)
        
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_data = yaml.safe_load(f)
    except Exception as e:
        print(f"[ERROR] Failed to load manifest.yaml: {e}")
        sys.exit(1)
        
    # Dynamic version reading
    version = manifest_data.get("framework", {}).get("version", "1.3")
    print(f"[*] Validating ACDLC v{version} platform structure...")
    print("[SUCCESS] manifest.yaml loaded successfully.")
    
    required_files = manifest_data.get("required_files", [])
    if not required_files:
        print("[ERROR] No 'required_files' listed in manifest.yaml!")
        sys.exit(1)
        
    missing_files = []
    for rel_path in required_files:
        full_path = os.path.join(base_dir, rel_path.replace("/", os.sep))
        if not os.path.exists(full_path):
            missing_files.append(rel_path)
            print(f"[ERROR] Missing file: {rel_path}")
        else:
            print(f"[SUCCESS] File exists: {rel_path}")
            
    if missing_files:
        print(f"\n[ERROR] Structure Validation FAILED! {len(missing_files)} file(s) missing from layout.")
        sys.exit(1)
    else:
        print(f"\n[SUCCESS] Structure Validation PASSED! All ACDLC v{version} files successfully verified.")
        sys.exit(0)

if __name__ == "__main__":
    verify_structure()
