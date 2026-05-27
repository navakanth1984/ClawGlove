import os
import sys
import yaml
import json
from datetime import datetime

def compile_policies():
    """Compiles YAML policies into optimized JSON rule graphs and stamps last_updated telemetry."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    policies_dir = os.path.join(base_dir, "policies")
    compiled_dir = os.path.join(base_dir, "compiled-policies")
    registry_manifest_path = os.path.join(base_dir, "registry", "manifest.yaml")
    
    if not os.path.exists(compiled_dir):
        os.makedirs(compiled_dir)
        
    print(f"[*] Policy Compiler executing at: {policies_dir}")
    
    current_date = datetime.utcnow().strftime("%Y-%m-%d")
    print(f"[*] Dynamic Timestamp generated: {current_date}")
    
    policy_files = ["token-limits.yaml", "delegation-limits.yaml", "budget-limits.yaml"]
    for file in policy_files:
        src_path = os.path.join(policies_dir, file)
        if not os.path.exists(src_path):
            print(f"[ERROR] Source policy not found: {src_path}")
            sys.exit(1)
            
        try:
            with open(src_path, "r", encoding="utf-8") as f:
                raw_data = yaml.safe_load(f)
                
            # Inject compilation metadata into output rule graphs
            if "policy" not in raw_data:
                raw_data = {"policy": raw_data}
            raw_data["policy"]["metadata"] = {
                "compiled_at": current_date,
                "compiler_version": "1.5"
            }
            
            dest_name = file.replace(".yaml", ".json")
            dest_path = os.path.join(compiled_dir, dest_name)
            with open(dest_path, "w", encoding="utf-8") as f:
                json.dump(raw_data, f, indent=2)
                
            print(f"[SUCCESS] Compiled '{file}' into optimized JSON graph -> 'compiled-policies/{dest_name}'")
        except Exception as e:
            print(f"[ERROR] Compilation failed for {file}: {e}")
            sys.exit(1)
            
    # Inject dynamic timestamp into registry/manifest.yaml last_updated field
    if os.path.exists(registry_manifest_path):
        try:
            with open(registry_manifest_path, "r", encoding="utf-8") as f:
                manifest_data = yaml.safe_load(f)
                
            if "registry" in manifest_data:
                manifest_data["registry"]["last_updated"] = current_date
                
            with open(registry_manifest_path, "w", encoding="utf-8") as f:
                yaml.dump(manifest_data, f, default_flow_style=False, sort_keys=False)
                
            print(f"[SUCCESS] Dynamic Timestamp injected successfully inside 'registry/manifest.yaml' -> last_updated: '{current_date}'")
        except Exception as e:
            print(f"[ERROR] Failed to update registry/manifest.yaml timestamp: {e}")
            sys.exit(1)
            
    sys.exit(0)

if __name__ == "__main__":
    compile_policies()
