# Metrics: Quality Specifications & Benchmarks

To ensure high-quality software, the following standard quality benchmarks are enforced across the ACDLC pipeline.

---

## 1. Quality Gates & SLAs

| Metric | Target SLA | Critical Limit (Fail Gate) | Measurement Frequency |
| :--- | :--- | :--- | :--- |
| **Functional Pass Rate** | 100% | <100% | Every validation run |
| **Code Coverage** | >85% lines | <75% lines | Prior to production merge |
| **Response Latency** | Mean <2.0s | Max >5.0s | Automated profile test |
| **Lint Error Rate** | 0 errors | >0 errors | Before Stage 5 transition |
| **Documentation Sync** | 100% APIs documented | Missing type/desc in code | Manual/Agent check |

---

## 2. Code Smell and Abstraction Violations
We track coding quality through Karpathy violation counts:
1. **Abstraction Level**: Maximum nested abstraction depth allowed is **3**. If class/function architecture requires deep hierarchy inheritance, flag for refactoring.
2. **Magical Abstractions**: Zero magical behaviors (e.g. self-modifying code, implicit metaclasses).
3. **Local Reasoning Density**: Code files exceeding **400 lines** must be audited and partitioned into smaller self-contained modules.

---

## 3. Quality Metrics Calculations
- **Pass Rate**: $$\text{Pass Rate} = \frac{\text{Passed Test Cases}}{\text{Total Test Cases}} \times 100\%$$
- **Coverage Index**: Code coverage must evaluate all execution branches (statement, branch, path coverage).
