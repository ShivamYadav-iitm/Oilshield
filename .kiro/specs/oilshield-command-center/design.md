# Design Document: OilShield Command Center

## Overview

OilShield is a single-page, dark-mode command center that demonstrates a complete "signal to
recommendation" pipeline for India's crude oil supply chain. It is composed of three connected
modules — **Live Risk Radar**, **Disruption Scenario Simulator**, and **Adaptive Procurement
Recommender** — plus a **one-click end-to-end pipeline** that runs all stages in sequence and
reports its own latency.

The design is deliberately shaped around two competing pressures:

1. **It must look and behave like a production SaaS product** — clean layering, a provider
   abstraction over external data and the LLM, typed data models, deterministic fallbacks, and a
   folder structure that could grow. This is what earns Technical Excellence (20%) and
   Scalability (15%).
2. **It must be buildable in a hackathon by a beginner using heavy AI assistance.** So every
   "scalable" seam is implemented with the simplest thing that works (SQLite/JSON instead of a
   cluster, a rules-based math model instead of a trained one, free-tier LLMs) while keeping the
   seam clean enough to swap later.

### Design principles

- **Deterministic core, probabilistic edges.** The risk math, scenario impact math, and
  procurement scoring are pure, deterministic functions. Only signal extraction touches an LLM,
  and even that has a deterministic fallback (Requirement 2.3). This makes the system testable,
  demoable offline, and reproducible — critical for a live judged demo.
- **Everything degrades to simulated.** Any external dependency (news feeds, LLM) has a bundled
  realistic fallback and a visible `Data_Source_Mode` badge (Requirements 1.3, 4.4). The demo can
  never "go dark" because a Wi-Fi connection failed on stage.
- **Explicit, testable assumptions.** The scenario simulator surfaces every numeric assumption it
  uses and applies them through documented formulas (Requirement 6.2). Judges specifically reward
  explicit, testable scenario assumptions, so these are first-class data, not hidden constants.
- **Traceability.** Every risk score traces back to the signals that produced it, and every
  signal carries its source and timestamp (Requirements 2.4, 4.3).

### Technology choices and rationale

| Layer | Choice | Why (vs. alternatives) |
|-------|--------|------------------------|
| Frontend framework | **React + Vite + TypeScript** | Vite gives instant HMR and a trivial build; TypeScript catches shape errors in the many data models a beginner will juggle. vs. Next.js: we don't need SSR/routing, so Next.js adds config overhead with no demo benefit. |
| Styling | **TailwindCSS** | Utility classes make a polished dark-mode SaaS look achievable without hand-writing CSS or learning a component library's theming API. |
| Charts | **Recharts** | Declarative React components for the timeline/area/line charts in Requirement 6.6 and 10.2. vs. D3: far less code for standard charts. |
| Map | **react-leaflet + OpenStreetMap tiles** | Free, no API key or billing setup — removes a signup blocker for a beginner. Corridors are drawn as colored polylines (Requirement 4.1). Mapbox free tier is the fallback if custom styling is wanted, but OSM keeps setup to zero. |
| Animation | **Framer Motion** | Smooth panel transitions and the animated pipeline stepper make the UX feel premium (15% UX) with minimal code. |
| Icons | **lucide-react** | Consistent, lightweight icon set for status badges and module headers. |
| Backend | **Python FastAPI + Uvicorn** | Beginner-friendly, automatic OpenAPI docs (great for demoing the API), first-class async, and the best ecosystem for AI/LLM glue. vs. Node/Express: Python wins for the LLM and numeric work. |
| LLM provider | **Groq (primary), Google Gemini (secondary)** behind a provider abstraction | Both have generous free tiers. Groq is extremely fast (low `Pipeline_Latency`), Gemini is a reliable second. The abstraction lets us swap OpenAI/OpenRouter/HuggingFace without touching business logic, and a **deterministic non-LLM extractor** is always available as the final fallback (Requirement 2.3). |
| Storage | **SQLite (via SQLModel) with a JSON-file fallback** | Saved scenarios (Requirement 7) need only a tiny key/value-ish store. SQLite is a single file, zero server. The repository interface means JSON files work identically for the absolute-simplest setup. |
| Deployment | **Frontend on Vercel/Netlify, backend on Render/Railway; Dockerfile for portability** | All have free tiers. A Dockerfile documents the runtime and enables one-command local run. |

#### LLM cost / free-tier notes

- **Groq**: free tier with high requests-per-minute on open models (e.g., Llama 3.x). No cost for
  hackathon volume. Chosen as primary for latency.
- **Google Gemini**: free tier (Flash models) with a daily request allowance sufficient for a
  demo. Chosen as secondary.
- **Deterministic fallback**: zero cost, zero network. Used when no API key is configured, when a
  call fails/times out, or when running the offline demo. This guarantees the pipeline always
  completes (Requirements 2.3, 9.4).

The LLM is used **only** to extract structure from unstructured news text. All scoring and impact
math is deterministic Python, so LLM variability never changes the numeric results a judge sees.

## Architecture

OilShield is a two-tier application: a React SPA talking to a FastAPI backend over JSON/HTTP. The
backend is organized into a thin API layer, a service layer (the three modules plus the pipeline
orchestrator), and an abstraction layer over external providers (data feeds, LLM) and storage.

```mermaid
graph TB
    subgraph Frontend["Frontend — React + Vite + TS (dark-mode SPA)"]
        DASH[Dashboard Shell]
        RR[Risk Radar View<br/>map + ranked list]
        SS[Scenario Simulator View<br/>assumptions + timeline]
        PR[Procurement View<br/>ranked options]
        PIPE[Pipeline Runner<br/>stepper + latency]
        API_CLIENT[API Client]
    end

    subgraph Backend["Backend — FastAPI"]
        subgraph APILayer["API Layer (routers)"]
            R_SIG[/signals/]
            R_RISK[/risk/]
            R_SCEN[/scenarios/]
            R_PROC[/procurement/]
            R_PIPE[/pipeline/run/]
        end

        subgraph Services["Service Layer"]
            SIS[Signal_Ingestion_Service]
            LLMX[LLM_Extractor]
            RSE[Risk_Scoring_Engine]
            SIM[Scenario_Simulator]
            REC[Procurement_Recommender]
            ORCH[Pipeline Orchestrator]
        end

        subgraph Abstraction["Provider & Storage Abstraction"]
            DSRC[DataSource Provider<br/>live | simulated]
            LLMP[LLM Provider<br/>Groq | Gemini | Deterministic]
            REPO[Scenario Repository<br/>SQLite | JSON]
        end
    end

    subgraph External["External / Bundled"]
        NEWS[News/GDELT feeds]
        SIMDATA[(Bundled simulated JSON<br/>signals, routes, options)]
        LLMAPI[Groq / Gemini APIs]
        DB[(SQLite file)]
    end

    DASH --> RR & SS & PR & PIPE
    RR & SS & PR & PIPE --> API_CLIENT
    API_CLIENT -->|JSON/HTTP| APILayer

    R_SIG --> SIS
    R_RISK --> RSE
    R_SCEN --> SIM
    R_PROC --> REC
    R_PIPE --> ORCH
    ORCH --> SIS --> LLMX --> RSE
    ORCH --> SIM
    ORCH --> REC

    SIS --> DSRC
    LLMX --> LLMP
    SIM --> REPO
    REC --> DSRC

    DSRC --> NEWS
    DSRC --> SIMDATA
    LLMP --> LLMAPI
    LLMP -.deterministic fallback.-> SIS
    REPO --> DB
```

### Request/data flow

1. The SPA calls a backend endpoint (e.g. `POST /pipeline/run`).
2. The router validates input and delegates to a service.
3. Services call **only** the abstraction layer for I/O (data sources, LLM, storage), never
   external SDKs directly. This is the swap seam for scaling and for live-vs-simulated fallback.
4. Deterministic services (scoring, impact, recommendation) are pure functions of their inputs and
   return typed models.
5. The router serializes typed models to JSON; the SPA renders them.

### Why this layering matters for scalability (15%)

- The **DataSource** and **LLM** providers are interfaces. Today they return bundled JSON or call a
  free LLM tier; tomorrow they can call a paid AIS feed, a vector DB for RAG, or a hosted model —
  no service code changes.
- Services are stateless and pure where possible, so the backend scales horizontally behind a load
  balancer without session affinity.
- The **Scenario Repository** interface hides SQLite; swapping to Postgres is a one-file change.

## Components and Interfaces

Each component below lists the requirements it satisfies. Services depend on interfaces, not
concrete providers, so each can be tested in isolation with a fake provider.

### Frontend components

- **Dashboard Shell** — the dark-mode layout hosting all modules in one interface; owns global
  loading/error surfaces and the `Data_Source_Mode` provenance banner. *(Requirements 10.1, 10.4,
  10.5, 4.4)*
- **Risk Radar View** — a Leaflet map drawing each corridor as a colored polyline by status band,
  a ranked list of corridors/countries by risk score, and a detail drawer showing contributing
  signals with source and timestamp. *(Requirements 4.1, 4.2, 4.3, 3.5)*
- **Scenario Simulator View** — a scenario picker, an assumptions panel with validated inputs
  (sliders/number fields bounded to each assumption's valid range), a "Run" action, a Recharts
  timeline of projected values, and Save/Load controls. *(Requirements 5.1–5.5, 6.2, 6.6, 7)*
- **Procurement View** — a ranked table/cards of procurement options with each attribute and a
  plain-language rationale. *(Requirements 8.4, 8.5)*
- **Pipeline Runner** — a one-click control that triggers the end-to-end flow, an animated stepper
  showing each stage result as it completes, and a prominent `Pipeline_Latency` readout.
  *(Requirements 9.1, 9.2, 9.3)*
- **API Client** — a thin typed wrapper (fetch) that mirrors the backend models in TypeScript and
  centralizes error handling so views can show per-module errors. *(Requirement 10.5)*

### Backend services

- **Signal_Ingestion_Service** — pulls raw signals per configured source via the DataSource
  provider, normalizes each into a `Signal`, records `Data_Source_Mode`, falls back to simulated
  data on source failure, and fails the refresh on unnormalizable data. *(Requirements 1.1–1.6)*
- **LLM_Extractor** — sends signal text to the LLM provider to produce a structured
  `ExtractedSignal` (corridor/country, risk category, severity 0–100), labels unmappable signals
  "unclassified", falls back to the raw severity on LLM failure, and preserves source/timestamp.
  *(Requirements 2.1–2.4)*
- **Risk_Scoring_Engine** — aggregates classified `ExtractedSignal`s into a `Risk_Score` in [0,100]
  per corridor and country, assigns 0 when no signals exist, excludes unclassified signals, and
  bands each score (low/elevated/high). *(Requirements 3.1–3.4, 2.2)*
- **Scenario_Simulator** — provides predefined scenarios and their assumptions, validates
  adjustable assumption edits, computes `Impact_Result`s deterministically, enforces monotonicity
  and the SPR floor, and serializes/deserializes saved scenarios. *(Requirements 5, 6, 7)*
- **Procurement_Recommender** — generates `Procurement_Option`s, computes each
  `Recommendation_Score`, excludes options below the compatibility threshold, and returns them
  sorted with rationales. *(Requirements 8.1–8.5)*
- **Pipeline Orchestrator** — runs ingestion → scoring → scenario impact → procurement in sequence,
  captures each stage result, measures `Pipeline_Latency`, and surfaces linked scenario/procurement
  actions when a corridor enters the "high" band. *(Requirements 9.1–9.4)*

### Abstraction interfaces

```python
class DataSourceProvider(Protocol):
    def fetch_signals(self, source_id: str) -> list[RawSignal]: ...
    # raises DataSourceError -> service falls back to SimulatedDataSource

class LLMProvider(Protocol):
    def extract(self, text: str, known_targets: list[str]) -> ExtractedSignal: ...
    # raises LLMError/timeout -> service falls back to DeterministicExtractor

class ScenarioRepository(Protocol):
    def save(self, record: SavedScenario) -> str: ...       # returns id
    def load(self, scenario_id: str) -> SavedScenario: ...   # raises ScenarioLoadError
```

Concrete implementations: `LiveDataSource` / `SimulatedDataSource`; `GroqProvider` /
`GeminiProvider` / `DeterministicExtractor`; `SqliteScenarioRepository` / `JsonFileScenarioRepository`.

## Data Models

All models are defined once in Python (Pydantic/SQLModel) and mirrored in TypeScript. Field ranges
are enforced by validators so invalid states are unrepresentable.

```python
# ---- Signals ----
class RawSignal(BaseModel):
    source: str
    timestamp: datetime
    text: str
    raw_severity: float            # 0..100, source-provided hint
    hinted_target: str | None      # corridor/country name if the feed provides one

class Signal(BaseModel):
    id: str
    source: str
    timestamp: datetime
    text_summary: str
    target: str                    # Corridor or Supplier_Country name
    target_type: Literal["corridor", "country"]
    raw_severity: float            # 0..100
    data_source_mode: Literal["live", "simulated"]

class ExtractedSignal(BaseModel):
    signal_id: str
    source: str                    # carried through for traceability (R2.4)
    timestamp: datetime            # carried through for traceability (R2.4)
    target: str | None             # None => unclassified
    target_type: Literal["corridor", "country"] | None
    risk_category: str             # e.g. "geopolitical", "sanctions", "logistics"
    severity: float                # 0..100
    classified: bool               # False => excluded from scoring (R2.2)

# ---- Risk ----
class RiskScore(BaseModel):
    target: str
    target_type: Literal["corridor", "country"]
    score: float                   # 0..100 inclusive (R3.2)
    band: Literal["low", "elevated", "high"]   # R3.4
    contributing_signal_ids: list[str]         # traceability (R4.3)

# ---- Scenario ----
class ScenarioAssumption(BaseModel):
    key: str                       # e.g. "corridor_closure_pct"
    label: str
    value: float
    min_value: float
    max_value: float
    adjustable: bool
    unit: str                      # e.g. "%", "kbd", "days"

class Scenario(BaseModel):
    id: str
    name: str                      # e.g. "Strait of Hormuz partial closure"
    corridor: str
    assumptions: list[ScenarioAssumption]

class ImpactPoint(BaseModel):
    day: int
    refinery_run_rate_pct: float
    fuel_price_index: float
    spr_days_of_cover: float       # >= 0 (R6.4)
    gdp_index: float

class ImpactResult(BaseModel):
    scenario_id: str
    assumptions_used: list[ScenarioAssumption]     # displayed alongside results (R6.2)
    timeline: list[ImpactPoint]                    # over scenario duration (R6.6)
    summary: dict[str, float]                      # end-state deltas

class SavedScenario(BaseModel):
    version: int                   # for compatibility checks (R7.3)
    name: str
    assumptions: list[ScenarioAssumption]

# ---- Procurement ----
class ProcurementOption(BaseModel):
    id: str
    supplier_country: str
    crude_grade: str
    tanker_route: str
    spot_price_usd_bbl: float
    tanker_availability: float     # 0..1
    port_congestion: float         # 0..1 (higher = worse)
    grade_compatibility: float     # 0..1 (higher = better)
    recommendation_score: float    # 0..100
    rationale: str

# ---- Pipeline ----
class PipelineResult(BaseModel):
    signals: list[Signal]
    risk_scores: list[RiskScore]
    impact: ImpactResult | None
    recommendations: list[ProcurementOption]
    linked_actions: list[dict]     # surfaced when a corridor is "high" (R9.3)
    latency_ms: int                # Pipeline_Latency (R9.2)
    data_source_modes: dict[str, str]
```

### Scenario impact computation — explicit, testable assumptions

The impact model is a **deterministic, transparent cascade**. It is not a trained model; it is a
set of published elasticity-style constants applied to the scenario assumptions. Every constant is
displayed in the assumptions panel or documented here so a judge can audit exactly why a number
moved. These constants are illustrative demo defaults, not calibrated forecasts, and are stated as
such in the UI.

Inputs (per-scenario `ScenarioAssumption`s, all adjustable within ranges):

- `corridor_closure_pct` ∈ [0, 100] — fraction of the corridor's throughput lost.
- `production_cut_kbd` ∈ [0, 5000] — supply removed (thousand barrels/day), for OPEC+ scenarios.
- `duration_days` ∈ [1, 180] — scenario horizon.
- `corridor_import_share` ∈ [0, 1] — share of India's crude imports flowing through this corridor
  (constant per corridor, displayed but typically non-adjustable).
- `spr_start_days` ∈ [0, 120] — starting days-of-cover (default ~9–10 days for India-style buffer).

Derived supply shock:

```
supply_loss_fraction = clamp(
    corridor_import_share * (corridor_closure_pct / 100)
      + production_cut_kbd / TOTAL_IMPORT_KBD,
    0, 1)
```

Explicit cascade formulas (with `k_*` documented constants):

```
refinery_run_rate_pct(day) = clamp(100 - k_ref * supply_loss_fraction * 100, 0, 100)
fuel_price_index(day)      = 100 * (1 + k_price * supply_loss_fraction)
spr_days_of_cover(day)     = max(0, spr_start_days - day * supply_loss_fraction / drawdown_divisor)
gdp_index(day)             = 100 * (1 - k_gdp * supply_loss_fraction * (day / duration_days))
```

**Testable assumptions baked into the model** (these become correctness properties):

1. **Monotonicity in closure**: a higher `corridor_closure_pct` never *raises*
   `spr_days_of_cover` at any day, all else equal. Because `supply_loss_fraction` is
   non-decreasing in closure and appears with a non-negative coefficient in the SPR drawdown term
   (Requirement 6.3).
2. **SPR floor**: `spr_days_of_cover` is clamped at 0 and never negative (Requirement 6.4).
3. **Bounded outputs**: run rate stays in [0, 100]; indices stay non-negative.
4. **No-shock identity**: when `supply_loss_fraction == 0`, run rate = 100, fuel/GDP indices = 100,
   and SPR stays flat at `spr_start_days` — a sanity anchor for the demo.

### Procurement Recommendation_Score formula

Each attribute is normalized to [0, 1] where 1 is best, then combined with fixed weights that sum
to 1, scaled to [0, 100]:

```
price_score   = clamp((PRICE_CEILING - spot_price_usd_bbl) / (PRICE_CEILING - PRICE_FLOOR), 0, 1)
avail_score   = tanker_availability                      # already 0..1, higher better
congest_score = 1 - port_congestion                      # higher congestion => lower score
compat_score  = grade_compatibility                      # already 0..1, higher better

recommendation_score = 100 * (
      W_PRICE   * price_score
    + W_AVAIL   * avail_score
    + W_CONGEST * congest_score
    + W_COMPAT  * compat_score )

# Weights (documented, tunable): W_PRICE=0.35, W_AVAIL=0.20, W_CONGEST=0.15, W_COMPAT=0.30
# Exclusion rule (R8.3): if grade_compatibility < MIN_COMPAT (default 0.4), option is dropped.
```

Because all weights are non-negative and each sub-score is monotone in its attribute, the score
behaves intuitively: cheaper, more available, less congested, more compatible options rank higher.
Options are returned sorted by `recommendation_score` descending (Requirement 8.4).

### API endpoints

| Method & path | Purpose | Maps to |
|---------------|---------|---------|
| `POST /signals/refresh` | Run ingestion; return normalized signals + per-source `Data_Source_Mode` | R1, R4.4 |
| `GET /risk/scores` | Return current `RiskScore`s (corridors + countries), banded and ranked | R3, R4.2 |
| `GET /risk/{target}/signals` | Return contributing signals for a corridor/country | R4.3 |
| `GET /scenarios` | List predefined scenarios with assumptions | R5.1, R5.2 |
| `POST /scenarios/{id}/run` | Validate assumptions, compute `ImpactResult` | R5.3–5.5, R6 |
| `POST /scenarios/save` | Serialize and store a configured scenario | R7.1 |
| `GET /scenarios/saved/{id}` | Load and deserialize a saved scenario (round-trip) | R7.2, R7.3 |
| `POST /procurement/recommend` | Generate, score, filter, and rank `ProcurementOption`s | R8 |
| `POST /pipeline/run` | Run full pipeline in sequence; return staged results + `latency_ms` | R9 |

### Scalable folder structure

```
oilshield/
  backend/
    app/
      main.py                # FastAPI app, CORS, router registration
      api/                   # thin routers (signals, risk, scenarios, procurement, pipeline)
      services/              # ingestion, extractor, scoring, simulator, recommender, orchestrator
      providers/             # datasource/, llm/, storage/  (interfaces + concrete impls)
      models/                # pydantic/sqlmodel models (shared shapes)
      core/                  # config, constants (k_*, weights), errors
      data/                  # bundled simulated JSON (signals, routes, options, corridors)
    tests/
      unit/                  # example + edge-case tests
      properties/            # property-based tests (Hypothesis)
    Dockerfile
    pyproject.toml
  frontend/
    src/
      components/            # dashboard shell, badges, timeline, map, stepper
      views/                 # RiskRadar, ScenarioSimulator, Procurement, PipelineRunner
      api/                   # typed client mirroring backend models
      types/                 # TS mirrors of data models
      lib/                   # formatting, color-by-band helpers
      App.tsx  main.tsx
    tests/                   # component + property tests (fast-check)
    index.html  vite.config.ts  tailwind.config.js
  README.md
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a
system — essentially, a formal statement about what the system should do. Properties serve as the
bridge between human-readable specifications and machine-verifiable correctness guarantees.*

The properties below were derived from the acceptance-criteria prework. Criteria that are UI
rendering, aesthetics, performance timing, configuration presence, or pure external-service
behavior are covered by unit/component/integration tests in the Testing Strategy instead, since a
meaningful "for all inputs" statement does not apply to them.

### Property 1: Signal normalization completeness

*For all* well-formed raw signals, normalizing a raw signal produces a `Signal` whose `source`,
`timestamp`, `text_summary`, `target`, `target_type`, and `raw_severity` are all populated, and
whose `source` and `timestamp` equal those of the raw signal.

**Validates: Requirements 1.2**

### Property 2: Malformed signals fail the refresh

*For all* raw signals that cannot be normalized (missing required fields, unparseable timestamp, or
severity outside 0–100), the ingestion refresh fails and reports that signal rather than silently
dropping or coercing it.

**Validates: Requirements 1.4**

### Property 3: Extracted severity is bounded and well-formed

*For all* signal texts processed by the deterministic extractor, the produced `ExtractedSignal` has
a `severity` in the inclusive range [0, 100] and includes a `risk_category`.

**Validates: Requirements 2.1**

### Property 4: Extraction preserves evidence traceability

*For all* signals, the resulting `ExtractedSignal` carries a `source` and `timestamp` identical to
the originating signal's `source` and `timestamp`.

**Validates: Requirements 2.4**

### Property 5: Unclassified signals do not affect scoring

*For all* sets of extracted signals, computing risk scores over the full set yields the same
`RiskScore` for every target as computing scores over only the classified subset — i.e. adding
unclassified signals never changes any score.

**Validates: Requirements 2.2**

### Property 6: Risk score completeness and zero-default

*For all* sets of extracted signals, the output contains exactly one `RiskScore` for every known
corridor and supplier country, and any target with no classified contributing signals receives a
score of exactly 0.

**Validates: Requirements 3.1, 3.3**

### Property 7: Risk scores are bounded

*For all* sets of extracted signals, every produced `RiskScore.score` lies in the inclusive range
[0, 100].

**Validates: Requirements 3.2**

### Property 8: Band classification is total and correct

*For all* scores in [0, 100], the assigned band is exactly "low" for 0–33, "elevated" for 34–66,
and "high" for 67–100, with no score left unbanded and no overlap at the boundaries.

**Validates: Requirements 3.4**

### Property 9: Risk ranking is ordered

*For all* sets of risk scores, the ranked list of corridors and supplier countries is ordered by
score from highest to lowest (non-increasing).

**Validates: Requirements 4.2**

### Property 10: In-range assumption edits are applied

*For all* adjustable assumptions and *for all* submitted values within that assumption's
[min_value, max_value] range, applying the value results in the assumption's current value equal to
the submitted value.

**Validates: Requirements 5.4**

### Property 11: Out-of-range assumption edits are rejected

*For all* adjustable assumptions and *for all* submitted values outside the [min_value, max_value]
range (or otherwise invalid), the submission is rejected and the assumption's current value is
unchanged from its previous valid value.

**Validates: Requirements 5.5**

### Property 12: Impact result structure and timeline length

*For all* valid scenario configurations, running the scenario produces an `ImpactResult` in which
every timeline point has a refinery run rate, fuel price index, SPR days-of-cover, and GDP index,
and the timeline contains exactly one point per day of the scenario's `duration_days`.

**Validates: Requirements 6.1, 6.6**

### Property 13: Impact result reports the assumptions used

*For all* scenario runs, the `ImpactResult.assumptions_used` equals the set of assumption values
that were applied to that run.

**Validates: Requirements 6.2**

### Property 14: SPR days-of-cover is monotonic in corridor closure

*For all* scenarios and *for all* pairs of closure percentages c1 < c2 with all other assumptions
unchanged, the SPR days-of-cover computed at c2 is less than or equal to the SPR days-of-cover
computed at c1 at every day of the timeline.

**Validates: Requirements 6.3**

### Property 15: SPR days-of-cover is non-negative

*For all* scenario configurations (including extreme closure percentages and durations), every SPR
days-of-cover value in the resulting timeline is greater than or equal to 0.

**Validates: Requirements 6.4**

### Property 16: Scenario save/load round-trip

*For all* configured scenarios, deserializing the serialized representation produces a scenario with
a name and assumption values identical to those that were saved.

**Validates: Requirements 7.1, 7.2**

### Property 17: Malformed saved scenarios are rejected

*For all* stored representations that are malformed, version-incompatible, or otherwise
undeserializable, loading raises a descriptive error rather than returning a partial or default
scenario.

**Validates: Requirements 7.3**

### Property 18: Recommendation score is bounded and monotonic in each attribute

*For all* procurement options, the `Recommendation_Score` lies in [0, 100]; and improving any single
attribute while holding the others fixed (lower spot price, higher tanker availability, lower port
congestion, or higher grade compatibility) never decreases the score.

**Validates: Requirements 8.2**

### Property 19: Compatibility threshold filter

*For all* generated sets of procurement options, no option in the recommended (returned) set has a
`grade_compatibility` below the defined minimum threshold.

**Validates: Requirements 8.3**

### Property 20: Recommendations are ordered by score

*For all* generated sets of procurement options, the returned list is ordered by
`Recommendation_Score` from highest to lowest (non-increasing).

**Validates: Requirements 8.4**

### Property 21: Recommendations include all attributes and a rationale

*For all* recommended procurement options, the rendered option includes the spot price, tanker
availability, port congestion, grade compatibility, and a non-empty plain-language rationale.

**Validates: Requirements 8.5**

### Property 22: High-band corridors surface a linked action

*For all* risk-score sets, for every corridor whose score falls in the "high" band, the pipeline
result's `linked_actions` contains at least one action referencing that corridor (a recommended
scenario and a procurement action).

**Validates: Requirements 9.3**

### Property 23: Timeline is chronologically ordered

*For all* sets of signal events and scenario projection points, the assembled timeline is ordered
chronologically (non-decreasing by timestamp/day).

**Validates: Requirements 10.3**

## Error Handling

Error handling follows the principle that **a demo must never hard-crash on stage**, while still
failing loudly for genuinely bad data so bugs are visible during development.

### Backend error strategy

- **Typed error hierarchy** in `core/errors.py`: `DataSourceError`, `LLMError`,
  `NormalizationError`, `ValidationError`, `ScenarioLoadError`. Each maps to a specific HTTP status
  via a FastAPI exception handler that returns a consistent JSON error envelope
  `{ "error": { "module": ..., "message": ..., "code": ... } }`.
- **Data source failure (R1.3)**: `DataSourceError` from a live source is caught inside
  `Signal_Ingestion_Service`, which transparently loads the bundled simulated data for that source
  and sets `Data_Source_Mode = "simulated"`. This is a *recovery*, not an error surfaced to the
  user — only the provenance badge changes.
- **Malformed raw data (R1.4)**: `NormalizationError` is *not* recovered. The refresh fails and the
  offending signal is reported, because silently coercing bad data would corrupt every downstream
  score.
- **LLM failure/timeout (R2.3)**: `LLMError` is caught in `LLM_Extractor`, which returns a
  deterministic fallback `ExtractedSignal` built from the signal's `raw_severity`. A short timeout
  (e.g. 3s) protects `Pipeline_Latency`.
- **Assumption validation (R5.5)**: out-of-range edits raise `ValidationError` before mutating
  state; the previous value is retained and the valid range is returned to the client.
- **Scenario load (R7.3)**: any deserialization failure raises `ScenarioLoadError` with a
  descriptive message; no partial scenario is returned.
- **Pipeline isolation (R9, R10.5)**: the orchestrator wraps each stage; a stage failure is recorded
  against that stage and returned so the frontend can show a module-scoped error while preserving
  completed stages.

### Frontend error strategy

- The API client normalizes every error into `{ module, message }`.
- Each module view owns three states: `loading`, `error`, `data`. On failure it renders the error
  in place of its loading indicator and leaves sibling modules untouched (R10.4, R10.5).
- A global provenance banner reflects `Data_Source_Mode` so simulated fallbacks are always visible
  (R4.4).

## Testing Strategy

OilShield uses a **dual testing approach**: property-based tests verify the universal correctness
properties above across many generated inputs, while unit, component, and integration tests cover
concrete examples, UI behavior, error branches, and performance budgets. Both are necessary —
property tests prove the math and data invariants hold generally; example tests prove specific
wiring and rendering work.

### Property-based testing

- **Backend library**: **Hypothesis** (Python). **Frontend library**: **fast-check** (TypeScript).
  Property-based testing is not implemented from scratch.
- Each of the 23 correctness properties is implemented by a **single** property-based test.
- Each property test runs a **minimum of 100 iterations**.
- Each property test is tagged with a comment in the format:
  `# Feature: oilshield-command-center, Property {number}: {property_text}`
- Custom generators produce: valid/invalid `RawSignal`s, mixes of classified/unclassified
  `ExtractedSignal`s, scores across [0,100] and out of range, scenarios with varying closure and
  duration (including extremes for the SPR floor and monotonicity properties), option sets with
  random attributes, and event sets for timeline ordering.
- The monotonicity property (14) generates a scenario plus an ordered pair of closure values; the
  round-trip property (16) generates arbitrary scenarios and asserts `load(save(s)) == s`.

### Unit and example tests (non-PBT criteria)

- Ingestion invokes each configured source (1.1); simulated load from bundled files (1.5); mode map
  populated per source (1.6); data-source fallback branch (1.3); LLM fallback branch (2.3).
- Band-to-color helper mapping (4.1); scenario catalog contains the three named scenarios (5.1);
  adjustable input control bounds (5.3).

### Component tests (frontend, UI behavior)

- Single dark-mode shell renders all three modules (10.1); map/charts/badges present (10.2);
  updated scores/bands after refresh (3.5); selecting a target shows contributing signals with
  source/timestamp (4.3); provenance badges (4.4); assumptions listed before run (5.2); loading
  indicators (10.4); module-scoped error isolation with preserved sibling results (10.5).

### Integration tests

- Pipeline runs the four stages in order and returns each stage result using fake providers (9.1);
  latency is reported and non-negative (9.2).

### Performance tests

- Scenario impact computes within 5 seconds (6.5).
- Full end-to-end pipeline completes within 15 seconds in fully simulated mode (9.4).

### Test data and reproducibility

- Bundled simulated JSON datasets (signals, corridors, routes, procurement options) double as
  deterministic fixtures, so the offline demo and the test suite exercise the same data paths and
  results are reproducible during judging.
