import os
import sys
import yaml

def validate_skill_yaml():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    skill_path = os.path.join(base_dir, "SKILL.md")
    
    print(f"[*] Validating YAML Frontmatter in: {skill_path}")
    
    if not os.path.exists(skill_path):
        print(f"[ERROR] SKILL.md does not exist at {skill_path}!")
        sys.exit(1)
        
    with open(skill_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    # Extract YAML frontmatter
    yaml_lines = []
    in_frontmatter = False
    delimiter_count = 0
    
    for line in lines:
        if line.strip() == "---":
            delimiter_count += 1
            if delimiter_count == 1:
                in_frontmatter = True
                continue
            elif delimiter_count == 2:
                in_frontmatter = False
                break
        if in_frontmatter:
            yaml_lines.append(line)
            
    if delimiter_count < 2:
        print("[ERROR] YAML Frontmatter delimiters (---) not fully found in SKILL.md!")
        sys.exit(1)
        
    yaml_content = "".join(yaml_lines)
    try:
        data = yaml.safe_load(yaml_content)
        print("[SUCCESS] YAML parsed successfully.")
    except Exception as e:
        print(f"[ERROR] Failed to parse YAML frontmatter: {e}")
        sys.exit(1)
        
    # Check required fields
    required_fields = ["name", "description"]
    missing = [field for field in required_fields if field not in data]
    
    if missing:
        print(f"[ERROR] Missing required frontmatter fields: {missing}")
        sys.exit(1)
    else:
        print(f"[SUCCESS] YAML Validation Passed! Found name: '{data['name']}' and description: '{data['description']}'")
        sys.exit(0)

if __name__ == "__main__":
    validate_skill_yaml()
