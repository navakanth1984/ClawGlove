# Workflows: Stage 0 - ALIGN Foundation

Everything begins here. Aligning intent, scoping requirements, and defining metrics ensures the AI agent understands both the destination and the strict constraints.

## Ã°Å¸â€ºÂ Ã¯Â¸ Step-by-Step Execution Plan

### Step 1: Extract Core Intent & Goals
Interact with the user to outline precisely what success looks like.
1. **Primary Goals**: Identify the top 2-3 essential business/product outcomes.
2. **Success Criteria**: Quantify these goals where possible (e.g., "process 1000 requests/min").

### Step 2: Unearth Root Problems
Agents frequently solve the wrong problem unless it is explicitly stated.
1. **Pain Points**: Document current user challenges.
2. **Root Causes**: Trace technical bottlenecks (e.g., "excessive latency due to multiple recursive calls").

### Step 3: Establish Scope & Bounds
This is the most critical agent instruction to prevent scope-creep.
1. **In-Scope**: Explicit list of modules, paths, and endpoints to build or modify.
2. **Strict Exclusions**: List what *not* to build, modify, or address. Any task outside this list must be halted.

### Step 4: Quantify Non-Functional Targets (Success Metrics)
Establish absolute bounds:
- **Accuracy**: Targeted successful completion rate.
- **Latency / Response Time**: Thresholds for operations.
- **Resource Constraints / Cost**: Cap per request or per run (Reasoning Economics).

### Step 5: Deliverable Generation & Machine-Readable Spec
Using the `templates/prd-template.md`, compile:
1. **Product Charter / PRD**: In the root of the workspace (e.g. `docs/prd.md`).
2. **Architecture Vision**: Describe the structural topology.

---

## Ã°Å¸â€â€™ Transition Gate to Stage 1
You **CANNOT** proceed to Stage 1 until:
- [ ] A Product Charter/PRD exists in the project path.
- [ ] Explicit Goals, Problems, and Exclusions are defined.
- [ ] The user has reviewed and approved the Stage 0 specification.
