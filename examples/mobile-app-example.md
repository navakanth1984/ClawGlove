# Examples: Mobile App Delivery Walkthrough

This walkthrough demonstrates the execution of the 7-stage ACDLC framework for building a high-fidelity **Task Management Mobile App** (React Native / Expo).

---

## Ã°Å¸â€â€ž The 7-Stage Execution Flow

### Stage 0: ALIGN Foundation
- **Goal**: Build an offline-first task manager with local notifications.
- **Problem**: Users lose tasks when they lose connection; notifications are delayed or missed.
- **Scope**:
  - *In-Scope*: React Native UI, WatermelonDB (for local persistence), Expo Notifications.
  - *Strict Exclusions*: No cloud synchronization backend, no real-time multi-user collaboration in V1.
- **Metrics**: 
  - Startup Latency: <1.5s
  - Offline Sync: 100% immediate writes to local SQL DB.
- **Deliverable**: Generated PRD under `docs/task_prd.md`.

### Stage 1: Context Engineering
- **Collection**: Gather Expo SDK 50 notifications guide, WatermelonDB schemas, and UI design rules.
- **Compression**: Reduce the 80-page WatermelonDB documentation into a single high-value file (`docs/melon_spec.md`) featuring core schema models, queries, and write patterns.
- **Prioritization**:
  - *Critical*: Database models, React Native state hooks.
  - *Optional*: Dynamic theme styling guides, splash screen details.
- **Bundle**: Compiled `docs/task_context_bundle.md`.

### Stage 2: Agentic Engineering
- **Planner Agent**: Orchestrates overall build tasks, managing milestones and tracking execution.
- **Researcher Subagent**: Traverses Expo SDK docs to extract notification setup steps.
- **Builder Subagent**: Modifies `App.js`, creates schema files, writes database hooks.
- **Reviewer Subagent**: Executes local Expo lint and mock unit tests.
- **Optimizer Subagent**: Identifies wasteful re-renders on the tasks listing screen.

### Stage 3: Controlled Execution
- **Task Scheduling**: Schema files must be fully written and validated before building components.
- **Reasoning Economics**: 
  - Routing layout changes to fast model (Gemini 3.5 Flash).
  - Routing database schema and hook validation to reasoning model (Gemini 3.1 Pro).
- **Recovery**: WatermelonDB compilation failed due to a missing Babel plugin. The Planner intercepted the crash log, appended the missing plugin to `babel.config.js`, re-ran the install, and verified successful build.

### Stage 4: Karpathy Development
- **Explicit over Clever**: Avoided dense inline styling hacks or complex custom state abstractions. State is represented via straightforward, transparent context hooks.
- **Readability**: Wrote clear, standard React Native components that are easy for both developers and LLM builders to parse.
- **Local Reasoning**: Put database query methods right inside the component module file to avoid hopping across 5 subdirectories.

### Stage 5: Verification & Validation
- **Specification Validation**: Checked that all features mapped to the PRD goals.
- **Functional Testing**: Ran `npm run test` yielding 100% pass rates.
- **Performance Testing**: Measured UI startup speed: **1.1 seconds** (satisfying the <1.5s SLA target).
- **Security Check**: Verified that no API keys or local developer tokens were checked in.

### Stage 6: Observability & Evolution
- **Log Review**: Total execution tokens consumed: **85,000**. The Babel plugin error cost **2 retries**.
- **Evolution Plan**: Added the missing Babel plugin directly to Stage 1 context schemas to prevent this error in subsequent React Native build cycles.
