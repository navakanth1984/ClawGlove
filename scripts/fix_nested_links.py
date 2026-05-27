import os
import re
import sys

def fix_nested_links():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print(f"[*] Commencing nested relative path calibrations sweep at: {base_dir}")
    
    # MD Link Regex: [text](link)
    md_link_regex = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
    
    extensions = (".md", ".yaml", ".json")
    fixed_count = 0
    
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if not file.endswith(extensions):
                continue
                
            file_path = os.path.join(root, file)
            rel_file_path = os.path.relpath(file_path, base_dir).replace(os.sep, "/")
            parts = rel_file_path.split("/")
            depth = len(parts) - 1
            
            if depth == 0:
                continue # Root level files don't need nesting corrections
                
            # Read contents
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                
            new_content = content
            matches = md_link_regex.findall(content)
            
            # Formulate parent directory jumps
            parent_jump = "../" * depth
            
            for text, link in matches:
                # Skip external links
                if link.startswith("http://") or link.startswith("https://") or link.startswith("mailto:") or link.startswith("#") or link.startswith("file:///"):
                    continue
                    
                # Skip if already relative to another directory (e.g. starts with ..)
                if link.startswith(".."):
                    continue
                    
                # If the link matches a required file in the manifest, we need to correct it to go up
                # e.g., if link is "SKILL.md", we convert to "../SKILL.md"
                # e.g., if link is "governance/context-limits.md", we convert to "../governance/context-limits.md"
                # Let's verify if the targets resolve to the correct root path
                potential_root_target = os.path.normpath(os.path.join(base_dir, link))
                if os.path.exists(potential_root_target):
                    new_link = parent_jump + link
                    # Replace in content (handling exact link syntax)
                    old_link_syntax = f"]({link})"
                    new_link_syntax = f"]({new_link})"
                    new_content = new_content.replace(old_link_syntax, new_link_syntax)
                    
            if new_content != content:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                print(f"[SUCCESS] Adjusted relative link jumps in: {rel_file_path}")
                fixed_count += 1
                
    print(f"\n[SUCCESS] Completed nested link calibrations sweep. Adjusted links in {fixed_count} file(s).")
    sys.exit(0)

if __name__ == "__main__":
    fix_nested_links()
