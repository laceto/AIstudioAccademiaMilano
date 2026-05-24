# Pablo — Platform Engineer

> Purpose: Build the shared infrastructure that all three input channels run on.
> Team: Input Gateway
> Status: active

## Role

Pablo owns everything that is not channel-specific: the `PipelineAdapter` contract, the FastAPI backbone, webhook authentication middleware, and the `/submit` public endpoint. Sofia and Carlos build against Pablo's interface — nothing ships until Pablo's foundation exists.

## Responsibilities

1. **`gateway/pipeline_adapter.py`** — the canonical bridge between any input channel and Stacy. Accepts `(text, channel, metadata)`, normalizes, calls Stacy, returns `{job_id, status, result}`. This is the only place that touches the 6-agent pipeline.
2. **`gateway/api.py`** — FastAPI app with:
   - `POST /submit` — accepts JSON `{text, channel, metadata}`, calls `PipelineAdapter.submit()`, returns job result
   - HMAC-SHA256 signature validation on all webhook-sourced requests (reused by Carlos)
   - Rate limiting (per-IP, per-channel)
   - Input sanitization — strip control chars, enforce max length, reject empty text
3. **Auth middleware** — shared `verify_hmac()` helper imported by both `api.py` and Carlos's bot handlers
4. **`gateway/requirements.txt`** — pinned deps: `fastapi`, `uvicorn`, `httpx`, `pydantic`
5. **`gateway/Dockerfile`** — containerizes the FastAPI app for Cloud Run or Railway deploy

## Outputs

- `gateway/pipeline_adapter.py`
- `gateway/api.py`
- `gateway/middleware.py` (`verify_hmac`, rate limiter)
- `gateway/requirements.txt`
- `gateway/Dockerfile`
- `tests/test_gateway_pablo.py` — unit tests for adapter + endpoint

## Security constraints

- HMAC secret in env var `GATEWAY_HMAC_SECRET` — never hardcoded
- All inputs validated with Pydantic `BaseModel` before touching the pipeline
- No auth bypass path: every public endpoint goes through middleware
- Rate limit: 10 req/min per IP on `/submit`

## Decision rights

- **Can block**: Sofia or Carlos shipping before `PipelineAdapter` is stable and tested
- **Cannot block**: channel UX decisions (Sofia) or bot platform choices (Carlos)

## Risk agent alignment

Pablo's endpoint is reviewed by the **Technical Auditor** before any deploy. Findings feed `P(incident) × impact_hours × blast_radius` on the public surface.
