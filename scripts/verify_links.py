import os
import re
import sys
import urllib.parse

def verify_links():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print(f"[*] Scanning relative & absolute markdown links at: {base_dir}")
    
    md_link_regex = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
    errors_found = 0
    scanned_files_count = 0
    links_checked_count = 0
    
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if not file.endswith(".md"):
                continue
            
            scanned_files_count += 1
            file_path = os.path.join(root, file)
            rel_file_path = os.path.relpath(file_path, base_dir)
            
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                
            matches = md_link_regex.findall(content)
            for text, link in matches:
                # Skip external links
                if link.startswith("http://") or link.startswith("https://") or link.startswith("mailto:") or link.startswith("#"):
                    continue
                
                links_checked_count += 1
                
                # Handle file:/// absolute paths
                if link.startswith("file:///"):
                    parsed_url = urllib.parse.urlparse(link)
                    # Convert file URL path to local Windows path
                    decoded_path = urllib.parse.unquote(parsed_url.path)
                    
                    # Fix: Added index boundary check to prevent out of range index exceptions
                    if len(decoded_path) > 2 and decoded_path.startswith('/') and (
                        decoded_path[2] == ':' or decoded_path[2] == '|'
                    ):
                        decoded_path = decoded_path[1:]
                    target_path = os.path.normpath(decoded_path)
                else:
                    # Resolve relative path
                    target_path = os.path.normpath(os.path.join(root, link))
                
                if not os.path.exists(target_path):
                    errors_found += 1
                    print(f"[ERROR] Broken Link in {rel_file_path}: [{text}]({link}) -> Target does not exist at: {target_path}")
                else:
                    pass # Pass verified link
                    
    print(f"\n[*] Summary: Scanned {scanned_files_count} markdown files. Checked {links_checked_count} internal links.")
    if errors_found > 0:
        print(f"[ERROR] Link integrity scan FAILED! {errors_found} broken link(s) found.")
        sys.exit(1)
    else:
        print("[SUCCESS] Link integrity scan PASSED! Zero broken links found.")
        sys.exit(0)

if __name__ == "__main__":
    verify_links()
