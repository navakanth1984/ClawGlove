# RFC-001: Manifest-Driven Architecture Specification

- **Author**: Platform Architect
- **Status**: APPROVED
- **Version Target**: ACDLC v1.2

---

## 1. Problem Space
Historically, verification files checked lists that were hardcoded directly inside script files. This caused code duplication, made upgrading stages fragile, and made it difficult for external tools to parse framework layouts.

## 2. Proposed System
Introduce a central YAML manifest `manifest.yaml` in the root platform directory. 

### Manifest Schema
```yaml
framework:
  name: ACDLC
  version: 1.2
required_files:
  - README.md
  - SKILL.md
```

## 3. Benefits
- Single source of truth.
- Zero code modifications required when adding playbooks/templates.
- Decouples static validation parameters.
