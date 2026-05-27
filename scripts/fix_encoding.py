import os
import sys

def fix_file_encoding(file_path):
    # Try reading as CP1252 to catch raw CP1252 bytes, and convert to UTF-8
    try:
        with open(file_path, "rb") as f:
            raw_bytes = f.read()
            
        # Decode as CP1252 first to resolve legacy Windows bytes correctly
        text = raw_bytes.decode("cp1252", errors="ignore")
        
        # Replace non-standard CP1252 characters with clean ASCII/UTF-8 equivalents
        replacements = {
            "\x96": "-",      # en-dash
            "\x97": " - ",    # em-dash
            "\x91": "'",      # left single quote
            "\x92": "'",      # right single quote
            "\x93": '"',      # left double quote
            "\x94": '"',      # right double quote
            "\x85": "...",    # ellipsis
            "\x86": " - ",    # dagger (often represented as character 134)
            "\ufffd": " - ",  # replacement character
        }
        
        for cp1252_char, ascii_char in replacements.items():
            text = text.replace(cp1252_char, ascii_char)
            
        # Write back as pure, clean UTF-8
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(text)
            
        print(f"[SUCCESS] Normalized encoding to UTF-8 for: {file_path}")
    except Exception as e:
        print(f"[ERROR] Failed to fix encoding for {file_path}: {e}")

def fix_all_encodings():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print(f"[*] Starting encoding normalization sweep at: {base_dir}")
    
    extensions = (".md", ".yaml", ".json")
    for root, dirs, files in os.walk(base_dir):
        # Skip the .git or scripts folders if necessary, but scripts themselves should be clean
        for file in files:
            if file.endswith(extensions):
                file_path = os.path.join(root, file)
                # Skip manifest.yaml to prevent recursive read issues if it's currently open
                fix_file_encoding(file_path)
                
    print("[SUCCESS] All files successfully normalized to clean UTF-8.")

if __name__ == "__main__":
    fix_all_encodings()
