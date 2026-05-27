# Workflows: Stage 1 - Context Engineering

Context is the source code of the agentic era. Loading excessive, unorganized raw data degrades agent outputs, triggers hallucination, and wastes financial resources.

## Ã°Å¸â€ºÂ Ã¯Â¸ Step-by-Step Execution Plan

### Step 1: Context Collection
1. Gather all files, specifications, documentation, and external references mapped during Stage 0.
2. Use tools like `grep_search` or graph traversal tools (`graphify`) to extract relevant dependencies.

### Step 2: Context Compression
Agents must convert heavy materials (e.g., extensive API manuals) into high-density reference markdown.
1. **Remove Boilerplate**: Prune licensing agreements, marketing text, and long narrative introductions.
2. **Tabular & Structured representation**: Convert narrative specifications into clean markdown tables, API JSON schemas, and structured lists.
3. **Goal**: Reduce 100 pages of raw information into 10 pages of high-fidelity, high-value context.

### Step 3: Context Prioritization
Sort context based on utility:
- **Priority 1 (Critical)**: Essential rules, schemas, runtime constraints, and environment specs.
- **Priority 2 (Important)**: Functional logic, endpoint routes, database schemas.
- **Priority 3 (Optional)**: Style guides, non-critical examples.

### Step 4: Packaging
Write the finalized context into the standardized template:
- Use `templates/context-bundle-template.md` to package the bundle.
- Label the bundle clearly (e.g. `docs/context-bundle-v1.md`).

---

## Ã°Å¸â€â€™ Transition Gate to Stage 2
You **CANNOT** proceed to Stage 2 until:
- [ ] Context Compression is executed (avoid loading raw API logs or massive files directly into subagent prompts).
- [ ] Priorities (Critical vs. Important vs. Optional) are clearly declared.
- [ ] A versioned Context Bundle is compiled and saved.
