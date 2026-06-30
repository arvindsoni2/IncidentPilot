# IncidentPilot MVP Gaps

This register separates accepted MVP constraints from defects. No open P0
safety or correctness blocker was found in the final review.

## P1 — address before broader distribution

### Reproducible dependency environment

The project declares compatible version ranges but has no lock file. The review
host's globally installed `pytest-asyncio` emits Python 3.14 deprecation
warnings even though the suite passes.

**Close when:** CI tests supported Python versions from a locked or otherwise
reproducible dependency set without unexpected plugin warnings.

### Database migrations

Schema creation currently uses SQLAlchemy `create_all`. This is sufficient for
a disposable local database but cannot safely evolve existing installations.

**Close when:** a migration tool and an upgrade/downgrade smoke test are
present.

### Automated live integration

Golden evaluations use deterministic fixture evidence. Adapter, workflow, UI,
and scenario behavior are separately tested, and scenarios were manually
verified, but CI does not run one end-to-end Compose failure-to-report test.

**Close when:** CI starts the demo stack, triggers each scenario, analyzes it,
checks the persisted report, and resets the stack.

## P2 — accepted local-MVP constraints

### Localhost-only security model

There is no authentication, authorization, or CSRF protection. This matches the
single-user localhost MVP decision and blocks shared/network deployment.

### External HTMX asset

The dashboard loads HTMX from a pinned CDN URL. Core HTML forms still work
without it, but partial updates need network access.

**Close when:** the asset is vendored locally with integrity/provenance
documented.

### Synchronous persistence in web requests

The MVP uses synchronous SQLAlchemy sessions. This is simple and reliable for a
single local user but can block under concurrent load.

### Eval history is file-based

Evaluation results are timestamped JSON files; the architecture source also
describes an `EvalRun` entity that is not implemented. File output satisfies
the current acceptance criteria but limits querying and trend analysis.

### Failed-analysis lifecycle

An `AgentRun` records failure, while its incident remains in `analyzing` with a
failure summary because the MVP incident status vocabulary has no `failed`
state. This is auditable but less clear operationally.

### Report timeline depth

Reports contain the required timeline section, but richer event timestamps and
cross-source correlation remain future work.

## Explicitly deferred

The following are not MVP gaps and must not be added casually:

- autonomous remediation;
- arbitrary shell execution;
- volume deletion;
- deployment rollback;
- approval workflows and action executors;
- multi-user or internet-facing operation.

Controlled self-healing design is Prompt 15 and remains deferred by owner
decision.
