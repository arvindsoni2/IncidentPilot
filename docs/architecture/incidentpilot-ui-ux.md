# IncidentPilot UI/UX Outline

## 1. UI Principle

Start with a minimal admin dashboard that is professional, clear, and easy for Codex to implement. Later polish toward a dark DevOps/SRE portfolio showcase.

## 2. Navigation

MVP navigation:

1. Dashboard
2. Services
3. Incidents
4. Reports
5. Settings

Later:

6. Evals

## 3. Dashboard Page

### Purpose

Show operational state at a glance.

### Sections

- Service health cards
- Active incidents
- Recent diagnoses
- Quick actions:
  - Analyze service
  - Trigger FS-001
  - Trigger FS-002
  - Reset scenarios

### Health Card Fields

- service name
- runtime
- status
- severity/criticality
- last check time
- health URL
- latest incident link

## 4. Services Page

### Purpose

Show monitored services and configuration.

### Table Columns

- service
- runtime
- container
- health URL
- polling interval
- criticality
- dependencies
- current status
- actions

### Actions

- Analyze
- View incidents
- View config

## 5. Incidents Page

### Purpose

Track incident lifecycle.

### Table Columns

- incident ID
- service
- severity
- status
- trigger
- summary
- detected at
- resolved at
- actions

### Filters

- service
- severity
- status
- date

## 6. Incident Detail Page

### Sections

1. Header
   - incident ID
   - service
   - severity
   - status
   - trigger
2. Timeline
   - detected
   - analysis started
   - evidence collected
   - diagnosis completed
   - resolved/closed
3. Evidence
   - container status
   - health result
   - dependency status
   - logs summary
   - metrics snapshot
   - deployment metadata
4. Ranked hypotheses
   - rank
   - cause
   - confidence
   - supporting evidence
5. Recommendations
   - action
   - safety policy
   - execution disabled in MVP
6. Report
   - rendered Markdown
   - copy
   - download Markdown
   - export JSON

## 7. Reports Page

### Purpose

Browse generated reports.

### Capabilities

- View Markdown report
- Copy Markdown
- Download Markdown
- Export structured JSON
- PDF later

## 8. Settings Page

### Purpose

Make runtime state transparent without editing config.

### Read-Only Sections

- Runtime
- Services
- LLM
- Database
- Safety policy
- Polling
- Security

## 9. HTMX Refresh

| Area | Behaviour |
|---|---|
| Service health cards | Refresh every 10–30 seconds |
| Incident list | Refresh every 30 seconds |
| Incident detail while analyzing | Partial refresh |
| Reports | Static after generated |

## 10. Visual Style

### MVP

- simple cards
- tables
- status badges
- confidence badges
- clean spacing
- readable Markdown report rendering

### Later Polish

- dark DevOps theme
- timeline visualisation
- evidence graph
- architecture diagram
- demo mode
- eval comparison cards
