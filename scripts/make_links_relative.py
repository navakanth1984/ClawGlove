import os
import sys

def convert_absolute_to_relative():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    abs_prefix = "file:///c:/Users/navka/navakanth001/.agents/skills/agentic-lifecycle-framework/"
    
    print(f"[*] Starting link portability sweep at: {base_dir}")
    print(f"[*] Replacing absolute path prefix: '{abs_prefix}' with relative linkages.")
    
    count = 0
    extensions = (".md", ".yaml", ".json")
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.endswith(extensions):
                file_path = os.path.join(root, file)
                
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    
                if abs_prefix in content:
                    # Perform replacement
                    content = content.replace(abs_prefix, "")
                    
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(content)
                        
                    print(f"[SUCCESS] Made links relative in: {os.path.relpath(file_path, base_dir)}")
                    count += 1
                    
    print(f"\n[SUCCESS] Sweep complete. Portability active in {count} file(s).")
    sys.exit(0)

if __name__ == "__main__":
    convert_absolute_to_relative()
