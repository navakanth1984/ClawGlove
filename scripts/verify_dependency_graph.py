import fnmatch
import os
import re
import sys
import urllib.parse
import yaml

STRICT_MODE = True # Strict Mode: Exits with 1 when circular dependency cycles exist

def find_links_in_file(file_path, base_dir):
    md_link_regex = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
        
    targets = []
    matches = md_link_regex.findall(content)
    for text, link in matches:
        if link.startswith("http://") or link.startswith("https://") or link.startswith("mailto:") or link.startswith("#"):
            continue
        
        # Handle file:/// absolute paths
        if link.startswith("file:///"):
            parsed_url = urllib.parse.urlparse(link)
            decoded_path = urllib.parse.unquote(parsed_url.path)
            if len(decoded_path) > 2 and decoded_path.startswith('/') and (
                decoded_path[2] == ':' or decoded_path[2] == '|'
            ):
                decoded_path = decoded_path[1:]
            target_path = os.path.normpath(decoded_path)
        else:
            target_path = os.path.normpath(os.path.join(os.path.dirname(file_path), link))
            
        # Case insensitive startswith check
        if os.path.exists(target_path) and target_path.lower().startswith(base_dir.lower()):
            rel_target = os.path.relpath(target_path, base_dir).replace(os.sep, "/")
            targets.append(rel_target)
            
    return targets

def verify_dependency_graph():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    manifest_path = os.path.join(base_dir, "manifest.yaml")
    
    print(f"[*] Validating Link Dependency Graph at: {base_dir}")
    
    # Load Ignore Patterns from manifest.yaml
    ignore_patterns = []
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest_data = yaml.safe_load(f)
            ignore_patterns = manifest_data.get("graph", {}).get("ignore_orphans", [])
            print(f"[SUCCESS] Loaded {len(ignore_patterns)} orphan ignore pattern(s) from manifest.")
        except Exception as e:
            print(f"[WARNING] Failed to parse manifest settings for graph: {e}")
            
    # 1. Build Adjacency List
    graph = {}
    all_files = []
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if not file.endswith(".md"):
                continue
            file_path = os.path.join(root, file)
            rel_file = os.path.relpath(file_path, base_dir).replace(os.sep, "/")
            all_files.append(rel_file)
            graph[rel_file] = find_links_in_file(file_path, base_dir)
            
    print(f"[*] Building node connections for {len(all_files)} markdown files...")
    
    # 2. Cycle Detection (DFS)
    visited = {} # None = unvisited, 1 = visiting, 2 = visited
    cycles = []
    
    def dfs(node, path):
        visited[node] = 1 # visiting
        path.append(node)
        
        for neighbor in graph.get(node, []):
            if visited.get(neighbor) == 1:
                # Cycle found!
                cycle_start = path.index(neighbor)
                cycle_path = path[cycle_start:] + [neighbor]
                cycles.append(" -> ".join(cycle_path))
            elif neighbor not in visited:
                dfs(neighbor, path)
                
        path.pop()
        visited[node] = 2 # visited
        
    for file in all_files:
        if file not in visited:
            dfs(file, [])
            
    # 3. Orphan Detection (using dynamic glob checks from manifest)
    inbound_counts = {file: 0 for file in all_files}
    for node, neighbors in graph.items():
        for neighbor in neighbors:
            if neighbor in inbound_counts:
                inbound_counts[neighbor] += 1
                
    orphans = []
    for file, count in inbound_counts.items():
        if count > 0 or file == "README.md":
            continue
            
        # Verify if file matches any ignore glob patterns
        ignored = False
        for pattern in ignore_patterns:
            if fnmatch.fnmatch(file, pattern):
                ignored = True
                break
                
        if not ignored:
            orphans.append(file)
            
    # 4. Final Platform Report
    print(f"\n[*] Graph Analysis Outcomes:")
    print(f"  - Total nodes: {len(all_files)}")
    print(f"  - Total edges: {sum(len(neighbors) for neighbors in graph.values())}")
    
    errors_found = 0
    warnings_found = 0
    
    if cycles:
        if STRICT_MODE:
            print("\n[ERROR] STRICT MODE ACTIVE: Circular references detected:")
            for cycle in cycles:
                print(f"  - Cycle: {cycle}")
                errors_found += 1
        else:
            print("\n[WARNING] Circular references detected:")
            for cycle in cycles:
                print(f"  - Cycle: {cycle}")
                warnings_found += 1
            
    if orphans:
        print("\n[WARNING] Orphan files detected (unlinked in active workflows/docs):")
        for orphan in orphans:
            print(f"  - Orphan: {orphan}")
            warnings_found += 1
            
    if errors_found > 0:
        print(f"\n[ERROR] Graph validation FAILED! circular dependency cycles detected.")
        sys.exit(1)
    elif warnings_found > 0:
        print(f"\n[WARNING] Graph validation parsed with {warnings_found} structural warning(s).")
        sys.exit(0)
    else:
        print("\n[SUCCESS] Link Dependency Graph is fully clean! Zero cycles or orphaned documents found.")
        sys.exit(0)

if __name__ == "__main__":
    verify_dependency_graph()
