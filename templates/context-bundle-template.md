# ACDLC Context Bundle Spec: [Feature/System Name]

## 1. Metadata Block
- **Bundle Version**: `1.0.0`
- **Scope Boundary**: `[Module / Path]`
- **Target Audience / Agent Role**: `[e.g., Builder / Researcher]`
- **Source Files Referenced**: 
  - [verify_structure.py](../scripts/verify_structure.py)
  - [verify_links.py](../scripts/verify_links.py)

---

## 2. Priority 1: CRITICAL CONTEXT (Must Load First)
*These details are essential for runtime safety and correct operations. If context budget is constrained, load ONLY this section.*

### Strict Technical Constraints
- Constraint A:
- Constraint B:

### Dynamic Environment Spec
- Active Node/Python Version:
- Core Third-Party Dependencies:

---

## 3. Priority 2: IMPORTANT CONTEXT (Feature & Logic Spec)
*High-value business logic requirements, API specifications, and routing rules.*

### Core Feature Definitions
- Feature Spec:

### Interface Contracts / API Specifications
```json
{
  "request": "...",
  "response": "..."
}
```

---

## 4. Priority 3: OPTIONAL CONTEXT (Style, Examples & Best Practices)
*Code examples, auxiliary guidelines, and non-breaking design specs that can be safely pruned to optimize context windows.*

### Code Examples & Conventions
```python
# Follow Karpathy style - Keep it simple, clear, and readable
```
