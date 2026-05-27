# Examples: High-Throughput Data Platform Delivery Walkthrough

This walkthrough demonstrates the execution of the 7-stage ACDLC framework for building a high-throughput **Real-time Event Processing Platform** (FastAPI / ClickHouse / Redis).

---

## Ã°Å¸â€â€ž The 7-Stage Execution Flow

### Stage 0: ALIGN Foundation
- **Goal**: Ingest 50,000 telemetry events per second with sub-second analytical write speeds.
- **Problem**: Traditional PostgreSQL ingestion locks up and fails under peak telemetry flows.
- **Scope**:
  - *In-Scope*: FastAPI telemetry ingest endpoint, Redis buffer queue, ClickHouse batch-write consumer.
  - *Strict Exclusions*: No real-time dashboard UI, no historical data migrations in V1.
- **Metrics**:
  - Ingestion Latency: <50ms per event.
  - Write Throughput: >50,000 events/sec.
  - Budget Limit: <$0.02 per 10k processed events.
- **Deliverable**: Generated PRD under `docs/data_platform_prd.md`.

### Stage 1: Context Engineering
- **Collection**: Gather ClickHouse batch client configuration details, Redis stream structures, and FastAPI performance guidelines.
- **Compression**: Reduce hundreds of pages of ClickHouse documentation into a dense, high-fidelity reference file (`docs/clickhouse_performance.md`) outlining batch-insert settings, cluster connection policies, and buffer size calculations.
- **Prioritization**:
  - *Critical*: ClickHouse batch engine setup, FastAPI asynchronous event loop config.
  - *Optional*: Schema validation libraries (Pydantic models for optional attributes).
- **Bundle**: Compiled `docs/data_platform_context.md`.

### Stage 2: Agentic Engineering
- **Planner Agent**: Manages the pipeline workflow, verifying component integrations.
- **Researcher Subagent**: Explores optimal FastAPI async thread pools.
- **Builder Subagent**: Writes Redis ingest code, ClickHouse batch writers, and fastapi configurations.
- **Reviewer Subagent**: Executes load testing mock simulations and verifies lint.
- **Optimizer Subagent**: Tunes Redis connection pooling configurations to prevent connection drops.

### Stage 3: Controlled Execution
- **Task Scheduling**: ClickHouse Batch Writer must be implemented and tested before creating the FastAPI ingestion route.
- **Reasoning Economics**:
  - Routed ClickHouse table schemas and memory allocations to deep reasoning models (Gemini 3.1 Pro).
  - Routed FastAPI route endpoints and basic configurations to fast model (Gemini 3.5 Flash).
- **Recovery**: ClickHouse batch insertions crashed due to a socket timeout under stress testing. The Planner intercepted the trace, determined it was a batch sizes overflow, tuned the batch size dynamically from 50k to 10k, and verified recovery.

### Stage 4: Karpathy Development
- **Explicit over Clever**: Kept Redis batch consumers unrolled. Wrote plain, explicit async loops instead of complex thread decorators.
- **Readability**: Code utilizes simple type hinting and explicit log traces. Avoided complex generic classes.
- **Local Reasoning**: Packaged the ClickHouse connection, validation, and batch write functions inside a single self-contained script (`batch_writer.py`) that fits entirely within the active context window.

### Stage 5: Verification & Validation
- **Specification Validation**: Confirmed batch ingests work offline and scale as defined in the PRD.
- **Functional Testing**: Ran tests: `pytest tests/` (100% success rate).
- **Performance Testing**: Ran high-load mock ingest:
  - Throughput: **58,000 events/sec** (satisfying the >50,000 target SLA).
  - Average Latency: **38 milliseconds** (satisfying the <50ms SLA target).
- **Security Check**: Scanned code to ensure zero active passwords or DB endpoints were hardcoded in the codebase.

### Stage 6: Observability & Evolution
- **Log Review**:clickhouse socket timeout error cost 3 retries and resolved by reducing batch size.
- **Evolution Plan**: Updated the `clickhouse_performance.md` context bundle spec to require a max batch limit of 10,000 events to prevent timeouts in subsequent database operations.
