import os
import sys
import yaml

def validate_policies():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    policies_dir = os.path.join(base_dir, "policies")
    
    print(f"[*] Validating platform policies at: {policies_dir}")
    
    # 1. Validate Token Limits
    token_limits_path = os.path.join(policies_dir, "token-limits.yaml")
    if not os.path.exists(token_limits_path):
        print(f"[ERROR] Missing token-limits.yaml policy!")
        sys.exit(1)
        
    try:
        with open(token_limits_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        rules = data["policy"]["rules"]
        ceiling = rules["active_token_ceiling"]
        ratio = rules["smart_truncation_trigger_ratio"]
        
        if ceiling <= 0:
            raise ValueError(f"active_token_ceiling must be positive, got: {ceiling}")
        if not (0.0 <= ratio <= 1.0):
            raise ValueError(f"smart_truncation_trigger_ratio must be between 0 and 1, got: {ratio}")
            
        print("[SUCCESS] token-limits.yaml policy rules validated.")
    except Exception as e:
        print(f"[ERROR] Failed to validate token-limits.yaml: {e}")
        sys.exit(1)
        
    # 2. Validate Delegation Limits
    delegation_limits_path = os.path.join(policies_dir, "delegation-limits.yaml")
    if not os.path.exists(delegation_limits_path):
        print(f"[ERROR] Missing delegation-limits.yaml policy!")
        sys.exit(1)
        
    try:
        with open(delegation_limits_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        rules = data["policy"]["rules"]
        depth = rules["max_delegation_tree_depth"]
        workers = rules["max_parallel_workers_count"]
        
        if depth <= 0:
            raise ValueError(f"max_delegation_tree_depth must be positive, got: {depth}")
        if workers <= 0:
            raise ValueError(f"max_parallel_workers_count must be positive, got: {workers}")
            
        print("[SUCCESS] delegation-limits.yaml policy rules validated.")
    except Exception as e:
        print(f"[ERROR] Failed to validate delegation-limits.yaml: {e}")
        sys.exit(1)
        
    # 3. Validate Budget Limits
    budget_limits_path = os.path.join(policies_dir, "budget-limits.yaml")
    if not os.path.exists(budget_limits_path):
        print(f"[ERROR] Missing budget-limits.yaml policy!")
        sys.exit(1)
        
    try:
        with open(budget_limits_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        rules = data["policy"]["rules"]
        ratio = rules["max_project_budget_spent_ratio"]
        sequence = rules["max_tool_calls_sequence_limit"]
        
        if not (0.0 <= ratio <= 1.0):
            raise ValueError(f"max_project_budget_spent_ratio must be between 0 and 1, got: {ratio}")
        if sequence <= 0:
            raise ValueError(f"max_tool_calls_sequence_limit must be positive, got: {sequence}")
            
        print("[SUCCESS] budget-limits.yaml policy rules validated.")
    except Exception as e:
        print(f"[ERROR] Failed to validate budget-limits.yaml: {e}")
        sys.exit(1)
        
    print("\n[SUCCESS] Platform Policy Validation PASSED! All rules satisfy safety bounds.")
    sys.exit(0)

if __name__ == "__main__":
    validate_policies()
