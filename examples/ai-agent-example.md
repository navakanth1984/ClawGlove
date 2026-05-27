# Examples: Custom AI Agent Delivery Walkthrough

This walkthrough demonstrates the execution of the 7-stage ACDLC framework for building a custom **AI Code Refactoring Agent** (Node.js / LangChain / AST Parser).

---

## Ã°Å¸â€â€ž The 7-Stage Execution Flow

### Stage 0: ALIGN Foundation
- **Goal**: Build an AI agent that automatically detects Karpathy coding violation patterns in codebases and proposes concrete refactoring diffs.
- **Problem**: Codebases accumulate unreadable clever-abstractions and large files, making it hard for both humans and future agents to work on.
- **Scope**:
  - *In-Scope*: Parsing local files with Babel AST parser, evaluating structure against clean coding metrics, executing refactoring calls via LLM.
  - *Strict Exclusions*: No automated commit/push to git in V1 (must output proposed diffs for human review only).
- **Metrics**:
  - Analysis Latency: <15s per file.
  - Refactoring Precision: >90% of proposed changes must be syntactically valid and pass unit tests.
  - Token Cost: <$0.04 per processed file.
- **Deliverable**: Generated PRD under `docs/refactor_agent_prd.md`.

### Stage 1: Context Engineering
- **Collection**: Gather Babel parser API references, GFM diff syntax specs, and the core Karpathy coding rules.
- **Compression**: Reduce hundreds of pages of Babel documentation into a 5-page guide (`docs/babel_ast_reference.md`) capturing only the AST node types (FunctionDeclaration, ClassDeclaration, etc.) and node modification methods.
- **Prioritization**:
  - *Critical*: AST node parsing methods, Diff generation formats.
  - *Optional*: General AST visualization tools.
- **Bundle**: Compiled `docs/refactor_context.md`.

### Stage 2: Agentic Engineering
- **Planner Agent**: Orchestrates the overall parser integration, review, and verification.
- **Researcher Subagent**: Explores AST traversal libraries to select the most lightweight parser.
- **Builder Subagent**: Writes parser files, LLM prompts, and file-saving modules.
- **Reviewer Subagent**: Executes linting and verifies the syntax of output diffs.
- **Optimizer Subagent**: Optimizes AST memory traversal speeds.

### Stage 3: Controlled Execution
- **Task Scheduling**: Parser logic must be completed and unit-tested before coupling it to the LLM generation prompt.
- **Reasoning Economics**:
  - Routed complex AST node mapping and verification to deep reasoning models (Gemini 3.1 Pro).
  - Routed simple CLI argument parsing to fast model (Gemini 3.5 Flash).
- **Recovery**: AST Parser hit a recursion limit when analyzing deep nested code. The Planner detected the stack overflow, halted execution, and configured a dynamic AST depth limit constraint of **3** in the traversal setup, successfully resolving the crash.

### Stage 4: Karpathy Development
- **Explicit over Clever**: Kept AST tree traversal unrolled. Avoided dense, recursive generator functions where plain iterative loops work.
- **Readability**: Wrote clear, straightforward classes (e.g. `ViolationDetector`, `CodeRefactorer`).
- **Local Reasoning**: Avoided complex class hierarchy inheritances. The AST processor class is fully self-contained in one file.

### Stage 5: Verification & Validation
- **Specification Validation**: Checked that the agent output strictly formatting diffs without attempting git writes (complying with scope).
- **Functional Testing**: Ran `npm run test` (100% pass rate).
- **Performance Testing**: Measured file parsing and analysis speed: **4.8 seconds** (satisfying the <15s SLA target).
- **Security Check**: Verified that the agent cannot execute dynamic bash/shell commands injected inside input files (strict sanitization).

### Stage 6: Observability & Evolution
- **Log Review**: Recursion stack overflow error cost 1 retry. Total API run cost evaluated to **$0.02** per file (satisfying the <$0.04 target).
- **Evolution Plan**: Updated the AST parser's context instructions to enforce an absolute traversal depth constraint of 3 globally in subsequent agent versions.
