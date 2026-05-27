# Workflows: Framework Upgrade & Evolution



The ACDLC is a living platform. This playbook establishes standard operating procedures for upgrading framework configurations, schemas, and verification rules based on telemetry logs.



---



## Ã°Å¸â€â€ž The Platform Upgrade Cycle



```text

  [vCurrent] 

      Ã¢â€â€š

  Telemetry Logs (Stage 6 execution)

      Ã¢â€â€š

  Bottleneck/Anomaly Identified

      Ã¢â€â€š

  RFC Drafted (Proposed manifest/workflow changes)

      Ã¢â€â€š

  Test Validation Suite passed 100%

      Ã¢â€â€š

  Release Increment -> [vNext]

```



---



## Ã°Å¸â€ºÂ Ã¯Â¸ Step-by-Step Upgrading Plan



### Step 1: Telemetry Analysis

1. Review [metrics/telemetry-metrics.md](../metrics/telemetry-metrics.md) logs.

2. Locate modules or stages experiencing highest retry triggers, token spikes, or logic errors.



### Step 2: Request For Comment (RFC)

1. Formulate a description of the structural enhancement needed in the root framework directory.

2. If new files are introduced, add them to `manifest.yaml` under `required_files` to ensure structure validators trace them.



### Step 3: Run Validation Suite

Execute the full test suite in `scripts/`:

```powershell

python scripts/verify_structure.py

python scripts/validate_skill_yaml.py

python scripts/verify_links.py

python scripts/verify_dependency_graph.py

```

- Structure checker must yield 100% path discovery.

- Dependency graph checks must return **zero circular loops** and **zero orphan files**.



### Step 4: Release Increment

1. Update `manifest.yaml` framework version string (e.g. `version: 1.3`).

2. Update the version string in `schemas/lifecycle-state.json`.

3. Commit and log details inside your global Strategic Walkthrough.

