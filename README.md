> **Note**: This document was created with AI assistance (AI-generated).  
> Update it as the backend structure evolves.

# Backend Scaffold

Backend skeleton for the naming check service using `Python + FastAPI` and onion architecture.

## Layers

- `domain/`: core business concepts, entities, value objects, repository contracts, policies
- `application/`: use cases, DTOs, orchestration logic, ports/interfaces
- `infrastructure/`: database, search, ML, preprocessing, collectors, config
- `presentation/`: FastAPI entrypoints, routers, API schemas, dependencies
- `shared/`: cross-cutting helpers shared across layers

## Runtime-aligned structure

The backend still follows onion architecture, but the internal modules now reflect the updated runtime
contours from the architecture diagrams:

- `presentation/api/v1/routes/checks/`: synchronous Stage 1 HTTP entrypoints
- `presentation/api/v1/routes/webhooks/`: Stage 2 webhook callbacks
- `application/use_cases/stage1/`: internal check orchestration
- `application/use_cases/stage2/`: async dispatch and webhook callback processing
- `application/use_cases/offline/`: offline collection and refresh flows
- `domain/policies/`: pure business rules such as Stage 2 deduplication keys
- `infrastructure/async_pipeline/`: queue, worker, result delivery, async result store
- `infrastructure/collectors/`: external source collection adapters
- `infrastructure/observability/`: async monitoring and thresholds

## Planned business capabilities

- registration check for new namings
- text infringement check
- logo comparison
- offline data collection and preprocessing
- source aggregation and ranking

## Dependency rule

Outer layers may depend on inner layers:
- `presentation -> application -> domain`
- `infrastructure -> application / domain`
- `domain` does not depend on `application`, `infrastructure`, or `presentation`

## Test layout

Tests stay split by type, but now mirror the architecture more explicitly:

- `tests/unit/domain/`: pure business rules
- `tests/unit/application/`: orchestration logic and job preparation
- `tests/integration/api/`: HTTP routes for Stage 1
- `tests/integration/webhooks/`: Stage 2 webhook contract
