# Implementation Plan: OilShield Command Center

## Overview

This plan builds OilShield in small, incremental steps that always leave something runnable early.
It starts by scaffolding both the FastAPI backend and the React + Vite + TypeScript frontend, then
lays down the shared data models and the provider/storage abstraction. It intentionally implements
the **simulated / deterministic** concrete providers first (so the whole pipeline works offline),
wires up each backend service (ingestion → extraction → risk scoring → scenario simulation →
procurement → pipeline orchestrator), then connects the frontend views to the API. Live LLM
providers (Groq primary, Gemini secondary) are added last, behind the same abstraction, with a
graceful deterministic fallback.

Testing follows the design's dual strategy: property-based tests (Hypothesis on the backend,
fast-check on the frontend) cover the 23 correctness properties, and unit / component / integration
/ performance tests cover concrete wiring, UI behavior, error branches, and timing budgets. Every
property test carries the design's required tag comment:
`# Feature: oilshield-command-center, Property {number}: {property_text}` (or `//` in TypeScript).

All code examples use **Python (FastAPI + Pydantic/SQLModel, Hypothesis)** for the backend and
**TypeScript (React + Vite + Tailwind, fast-check)** for the frontend, matching the design.

## Tasks

- [x] 1. Scaffold the backend project skeleton
  - Create the `oilshield/backend/` folder structure from the design: `app/main.py`, `app/api/`,
    `app/services/`, `app/providers/`, `app/models/`, `app/core/`, `app/data/`, and `tests/unit/`,
    `tests/properties/`
  - Add `pyproject.toml` declaring FastAPI, Uvicorn, Pydantic, SQLModel, Hypothesis, pytest, and the
    HTTP client used for live providers
  - Implement a minimal `app/main.py` FastAPI app with CORS enabled and a `GET /health` route so the
    server boots and is demoable immediately
  - Add a `Dockerfile` that runs the app with Uvicorn
  - _Requirements: 10.1_

- [x] 2. Scaffold the frontend project shell
  - Create `oilshield/frontend/` with Vite + React + TypeScript, `index.html`, `vite.config.ts`,
    `tailwind.config.js`, and the `src/components/`, `src/views/`, `src/api/`, `src/types/`,
    `src/lib/` folders from the design
  - Configure TailwindCSS with a dark-mode theme as the base
  - Add dependencies: react-leaflet + leaflet, recharts, framer-motion, lucide-react, fast-check
  - Render a minimal dark-mode `App.tsx` shell (header + empty module regions) so `npm run dev` shows
    the command center chrome
  - _Requirements: 10.1_

- [x] 3. Define shared core config, constants, and errors (backend)
  - [x] 3.1 Implement `app/core/constants.py` with the documented model constants
    - Cascade constants `k_ref`, `k_price`, `k_gdp`, `drawdown_divisor`, `TOTAL_IMPORT_KBD`
    - Procurement weights `W_PRICE=0.35`, `W_AVAIL=0.20`, `W_CONGEST=0.15`, `W_COMPAT=0.30`,
      `PRICE_CEILING`, `PRICE_FLOOR`, and `MIN_COMPAT=0.4`
    - Risk band thresholds (low 0–33, elevated 34–66, high 67–100)
    - _Requirements: 3.4, 6.2, 8.2, 8.3_
  - [x] 3.2 Implement `app/core/errors.py` typed error hierarchy
    - Define `DataSourceError`, `LLMError`, `NormalizationError`, `ValidationError`,
      `ScenarioLoadError`
    - Add a FastAPI exception handler that returns the JSON error envelope
      `{ "error": { "module", "message", "code" } }` and register it in `main.py`
    - _Requirements: 10.5_
  - [x] 3.3 Implement `app/core/config.py`
    - Load settings for data-source mode, LLM provider selection, API keys, and LLM timeout (default 3s)
    - _Requirements: 1.3, 2.3_

- [ ] 4. Define shared data models
  - [x] 4.1 Implement Pydantic/SQLModel models in `app/models/`
    - `RawSignal`, `Signal`, `ExtractedSignal`, `RiskScore`, `ScenarioAssumption`, `Scenario`,
      `ImpactPoint`, `ImpactResult`, `SavedScenario`, `ProcurementOption`, `PipelineResult`
    - Add field validators enforcing documented ranges (severity/score in [0,100], availability /
      congestion / compatibility in [0,1], SPR days-of-cover >= 0)
    - _Requirements: 2.1, 3.2, 6.4, 8.2_
  - [x] 4.2 Mirror the models as TypeScript types in `frontend/src/types/`
    - One interface per backend model so the API client and views are type-checked
    - _Requirements: 10.1_

- [x] 5. Bundle simulated datasets
  - Create realistic simulated JSON files in `app/data/`: `signals.json`, `corridors.json`,
    `routes.json`, `procurement_options.json`
  - Include the corridors named in the design (Strait of Hormuz, Red Sea, Cape of Good Hope) and a
    set of supplier countries, each with `corridor_import_share` where applicable
  - These files double as deterministic test fixtures
  - _Requirements: 1.5, 4.1, 5.1, 8.1_

- [x] 6. Provider and storage abstraction (interfaces + deterministic/simulated implementations)
  - [x] 6.1 Define the abstraction interfaces in `app/providers/`
    - `DataSourceProvider`, `LLMProvider`, and `ScenarioRepository` protocols matching the design
      signatures
    - _Requirements: 1.1, 2.1, 7.1_
  - [x] 6.2 Implement `SimulatedDataSource` (datasource provider)
    - Load `RawSignal`s from the bundled JSON for a given `source_id`
    - _Requirements: 1.5_
  - [x] 6.3 Implement `DeterministicExtractor` (LLM provider fallback)
    - Map signal text to a known corridor/country via keyword rules, produce `risk_category` and a
      severity derived from the raw hint; return an unclassified result when no target matches
    - _Requirements: 2.1, 2.2, 2.3_
  - [ ]* 6.4 Write property test for the deterministic extractor severity bound
    - **Property 3: Extracted severity is bounded and well-formed**
    - **Validates: Requirements 2.1**
  - [x] 6.5 Implement `JsonFileScenarioRepository` and `SqliteScenarioRepository`
    - `save` returns an id; `load` raises `ScenarioLoadError` on any failure; both satisfy the same
      interface so either can back the simulator
    - _Requirements: 7.1, 7.2, 7.3_

- [x] 7. Signal ingestion and normalization service
  - [x] 7.1 Implement `Signal_Ingestion_Service` in `app/services/`
    - Iterate configured sources, fetch raw signals via the datasource provider, normalize each into
      a `Signal` (source, timestamp, text summary, target, target_type, raw severity)
    - On `DataSourceError`, fall back to `SimulatedDataSource` and set `Data_Source_Mode="simulated"`
      for that source; record the mode per source
    - Raise `NormalizationError` (fail the refresh, report the offending signal) on unnormalizable data
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.6_
  - [ ]* 7.2 Write property test for normalization completeness
    - **Property 1: Signal normalization completeness**
    - **Validates: Requirements 1.2**
  - [ ]* 7.3 Write property test for malformed-signal refresh failure
    - **Property 2: Malformed signals fail the refresh**
    - **Validates: Requirements 1.4**
  - [ ]* 7.4 Write unit tests for ingestion branches
    - Each configured source is invoked (1.1); simulated load from bundled files (1.5); mode map
      populated per source (1.6); data-source fallback branch (1.3)
    - _Requirements: 1.1, 1.3, 1.5, 1.6_

- [x] 8. LLM/deterministic extraction service
  - [x] 8.1 Implement `LLM_Extractor` service wired to the `LLMProvider` interface
    - Produce `ExtractedSignal` (target/target_type, risk_category, severity 0–100), label unmappable
      signals unclassified, carry through source and timestamp
    - On `LLMError`/timeout, fall back to a deterministic output built from `raw_severity`
    - _Requirements: 2.1, 2.2, 2.3, 2.4_
  - [ ]* 8.2 Write property test for evidence traceability
    - **Property 4: Extraction preserves evidence traceability**
    - **Validates: Requirements 2.4**
  - [ ]* 8.3 Write unit test for the LLM failure fallback branch
    - Simulate provider failure and assert the deterministic fallback output is used (2.3)
    - _Requirements: 2.3_

- [x] 9. Risk scoring engine and banding
  - [x] 9.1 Implement `Risk_Scoring_Engine` in `app/services/`
    - Aggregate classified `ExtractedSignal`s into a `RiskScore` in [0,100] per corridor and country,
      exclude unclassified signals, assign 0 when no signals exist, record contributing signal ids
    - Implement the band classifier (low 0–33, elevated 34–66, high 67–100)
    - _Requirements: 2.2, 3.1, 3.2, 3.3, 3.4_
  - [ ]* 9.2 Write property test that unclassified signals do not affect scoring
    - **Property 5: Unclassified signals do not affect scoring**
    - **Validates: Requirements 2.2**
  - [ ]* 9.3 Write property test for score completeness and zero-default
    - **Property 6: Risk score completeness and zero-default**
    - **Validates: Requirements 3.1, 3.3**
  - [ ]* 9.4 Write property test that risk scores are bounded
    - **Property 7: Risk scores are bounded**
    - **Validates: Requirements 3.2**
  - [ ]* 9.5 Write property test for band classification correctness
    - **Property 8: Band classification is total and correct**
    - **Validates: Requirements 3.4**

- [x] 10. Signals and risk API endpoints
  - [x] 10.1 Implement the signals router `POST /signals/refresh`
    - Run ingestion and return normalized signals plus per-source `Data_Source_Mode`
    - _Requirements: 1.1, 4.4_
  - [x] 10.2 Implement the risk router `GET /risk/scores` and `GET /risk/{target}/signals`
    - Return banded `RiskScore`s ranked highest-to-lowest, and contributing signals (with source and
      timestamp) for a selected target
    - _Requirements: 3.5, 4.2, 4.3_
  - [ ]* 10.3 Write property test for risk ranking order
    - **Property 9: Risk ranking is ordered**
    - **Validates: Requirements 4.2**

- [x] 11. Checkpoint - backend risk path runnable
  - Ensure all tests pass, ask the user if questions arise.

- [x] 12. Scenario configuration and assumption validation
  - [x] 12.1 Implement the scenario catalog in `Scenario_Simulator`
    - Provide the predefined scenarios (Strait of Hormuz partial closure, OPEC+ production cut,
      Red Sea shutdown) each with its `ScenarioAssumption` list and valid ranges
    - _Requirements: 5.1, 5.2_
  - [x] 12.2 Implement adjustable-assumption validation
    - Apply in-range submitted values as the new current value; reject out-of-range/invalid values,
      retain the previous valid value, and return the valid range (`ValidationError`)
    - _Requirements: 5.3, 5.4, 5.5_
  - [ ]* 12.3 Write property test for in-range assumption edits
    - **Property 10: In-range assumption edits are applied**
    - **Validates: Requirements 5.4**
  - [ ]* 12.4 Write property test for out-of-range assumption rejection
    - **Property 11: Out-of-range assumption edits are rejected**
    - **Validates: Requirements 5.5**

- [x] 13. Scenario impact cascade computation
  - [x] 13.1 Implement the deterministic impact cascade in `Scenario_Simulator`
    - Compute `supply_loss_fraction` and the documented per-day formulas for refinery run rate, fuel
      price index, SPR days-of-cover (clamped at 0), and GDP index using the `core/constants.py`
      values; build one `ImpactPoint` per day over `duration_days` and record `assumptions_used`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.6_
  - [ ]* 13.2 Write property test for impact structure and timeline length
    - **Property 12: Impact result structure and timeline length**
    - **Validates: Requirements 6.1, 6.6**
  - [ ]* 13.3 Write property test that the result reports the assumptions used
    - **Property 13: Impact result reports the assumptions used**
    - **Validates: Requirements 6.2**
  - [ ]* 13.4 Write property test for SPR monotonicity in corridor closure
    - **Property 14: SPR days-of-cover is monotonic in corridor closure**
    - **Validates: Requirements 6.3**
  - [ ]* 13.5 Write property test for the SPR non-negative floor
    - **Property 15: SPR days-of-cover is non-negative**
    - **Validates: Requirements 6.4**
  - [ ]* 13.6 Write performance test for scenario computation time
    - Assert an `Impact_Result` computes within 5 seconds
    - _Requirements: 6.5_

- [x] 14. Scenario save and restore
  - [x] 14.1 Implement save/load in `Scenario_Simulator` over the `ScenarioRepository`
    - Serialize scenario name and assumption values (`SavedScenario` with `version`); deserialize to
      an identical scenario; reject malformed/version-incompatible representations with a descriptive
      `ScenarioLoadError`
    - _Requirements: 7.1, 7.2, 7.3_
  - [ ]* 14.2 Write property test for the save/load round-trip
    - **Property 16: Scenario save/load round-trip**
    - **Validates: Requirements 7.1, 7.2**
  - [ ]* 14.3 Write property test that malformed saved scenarios are rejected
    - **Property 17: Malformed saved scenarios are rejected**
    - **Validates: Requirements 7.3**

- [x] 15. Scenario API endpoints
  - Implement the scenarios router: `GET /scenarios`, `POST /scenarios/{id}/run`,
    `POST /scenarios/save`, `GET /scenarios/saved/{id}`
  - Map validation failures to the JSON error envelope
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 6.1, 7.1, 7.2, 7.3_

- [x] 16. Procurement recommender
  - [x] 16.1 Implement `Procurement_Recommender` service
    - Generate `Procurement_Option`s from bundled data, compute each `Recommendation_Score` with the
      weighted normalized formula, drop options below `MIN_COMPAT`, return sorted descending with a
      plain-language rationale per option
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_
  - [x] 16.2 Implement the procurement router `POST /procurement/recommend`
    - _Requirements: 8.1, 8.4, 8.5_
  - [ ]* 16.3 Write property test for score bound and per-attribute monotonicity
    - **Property 18: Recommendation score is bounded and monotonic in each attribute**
    - **Validates: Requirements 8.2**
  - [ ]* 16.4 Write property test for the compatibility threshold filter
    - **Property 19: Compatibility threshold filter**
    - **Validates: Requirements 8.3**
  - [ ]* 16.5 Write property test that recommendations are ordered by score
    - **Property 20: Recommendations are ordered by score**
    - **Validates: Requirements 8.4**

- [x] 17. Pipeline orchestrator and end-to-end endpoint
  - [x] 17.1 Implement the `Pipeline Orchestrator` service
    - Run ingestion → scoring → scenario impact → procurement in sequence, capture each stage result,
      wrap each stage so a failure is recorded against that stage while completed stages are preserved,
      measure `latency_ms`, and populate `linked_actions` for corridors in the "high" band
    - _Requirements: 9.1, 9.2, 9.3, 10.5_
  - [x] 17.2 Implement the pipeline router `POST /pipeline/run`
    - Return the staged `PipelineResult` including `latency_ms` and `data_source_modes`
    - _Requirements: 9.1, 9.2_
  - [ ]* 17.3 Write property test that high-band corridors surface a linked action
    - **Property 22: High-band corridors surface a linked action**
    - **Validates: Requirements 9.3**
  - [ ]* 17.4 Write integration test for staged execution order
    - Use fake providers to assert the four stages run in order and each stage result is returned;
      assert latency is reported and non-negative
    - _Requirements: 9.1, 9.2_
  - [ ]* 17.5 Write performance test for end-to-end latency
    - Assert the full pipeline completes within 15 seconds in fully simulated mode
    - _Requirements: 9.4_

- [x] 18. Checkpoint - full backend pipeline runnable in simulated mode
  - Ensure all tests pass, ask the user if questions arise.

- [x] 19. Frontend API client and shared helpers
  - [~] 19.1 Implement the typed API client in `frontend/src/api/`
    - Wrap fetch for every backend endpoint, mirror response types, and normalize errors to
      `{ module, message }`
    - _Requirements: 10.5_
  - [~] 19.2 Implement `src/lib/` helpers
    - Band-to-color helper and formatting utilities used by badges, map, and charts
    - _Requirements: 4.1_
  - [ ]* 19.3 Write component test for the band-to-color helper
    - Verify each band maps to its expected color
    - _Requirements: 4.1_

- [x] 20. Dashboard shell and shared components
  - [~] 20.1 Implement the `Dashboard Shell` component
    - Dark-mode layout hosting all three modules, a global `Data_Source_Mode` provenance banner, and
      global loading/error surfaces
    - _Requirements: 10.1, 10.2, 4.4_
  - [~] 20.2 Implement shared components: status badge, timeline, map wrapper, animated stepper
    - Assemble the timeline in chronological order from signal events and scenario projection points
    - _Requirements: 10.2, 10.3_
  - [ ]* 20.3 Write property test for chronological timeline ordering
    - **Property 23: Timeline is chronologically ordered** (fast-check)
    - **Validates: Requirements 10.3**
  - [ ]* 20.4 Write component test for the shell
    - Single dark-mode shell renders all three modules; map/charts/badges present
    - _Requirements: 10.1, 10.2_

- [x] 21. Risk Radar view
  - [~] 21.1 Implement the `Risk Radar View`
    - Leaflet map drawing each corridor as a colored polyline by band, a ranked list of
      corridors/countries by score, a detail drawer showing contributing signals with source and
      timestamp, and the provenance badge; wire to `/risk/scores`, `/risk/{target}/signals`,
      `/signals/refresh`
    - _Requirements: 3.5, 4.1, 4.2, 4.3, 4.4_
  - [ ]* 21.2 Write component tests for Risk Radar behavior
    - Updated scores/bands after refresh (3.5); selecting a target shows contributing signals with
      source/timestamp (4.3); provenance badges shown (4.4)
    - _Requirements: 3.5, 4.3, 4.4_

- [x] 22. Scenario Simulator view
  - [~] 22.1 Implement the `Scenario Simulator View`
    - Scenario picker, assumptions panel with inputs bounded to each assumption's valid range, a Run
      action, a Recharts timeline of projected values, assumptions-used display, and Save/Load
      controls; wire to the scenarios endpoints
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 6.2, 6.6, 7.1, 7.2, 7.3_
  - [ ]* 22.2 Write component tests for the simulator
    - Assumptions listed before run (5.2); adjustable input control bounds (5.3)
    - _Requirements: 5.2, 5.3_

- [x] 23. Procurement view
  - Implement the `Procurement View` as ranked cards/table showing spot price, tanker availability,
    port congestion, grade compatibility, and rationale per option; wire to `/procurement/recommend`
  - _Requirements: 8.4, 8.5_
  - [ ]* 23.1 Write component test for procurement rendering
    - **Property 21: Recommendations include all attributes and a rationale** (fast-check over the
      rendered option list)
    - **Validates: Requirements 8.5**

- [x] 24. Pipeline Runner view and error/loading states
  - [~] 24.1 Implement the `Pipeline Runner View`
    - One-click trigger for `/pipeline/run`, an animated stepper showing each stage result as it
      completes, a prominent `Pipeline_Latency` readout, and surfaced linked actions for high-band
      corridors
    - _Requirements: 9.1, 9.2, 9.3_
  - [~] 24.2 Implement per-module loading and error isolation across all views
    - Each module shows a loading indicator while its computation is in progress; on failure it shows
      a module-scoped error in place of the loading indicator and preserves sibling module results
    - _Requirements: 10.4, 10.5_
  - [ ]* 24.3 Write component tests for loading and error isolation
    - Loading indicators shown during computation (10.4); module-scoped error with preserved sibling
      results (10.5)
    - _Requirements: 10.4, 10.5_

- [x] 25. Checkpoint - end-to-end demo works in simulated mode
  - Ensure all tests pass, ask the user if questions arise.

- [x] 26. Live provider implementations behind the abstraction
  - [~] 26.1 Implement `LiveDataSource` (news/GDELT feed) implementing `DataSourceProvider`
    - Fetch and shape raw signals; on failure raise `DataSourceError` so ingestion falls back to
      simulated data
    - _Requirements: 1.1, 1.3_
  - [~] 26.2 Implement `GroqProvider` (primary) and `GeminiProvider` (secondary) implementing `LLMProvider`
    - Call the free-tier APIs with the configured timeout; raise `LLMError` on failure/timeout so the
      extractor falls back to `DeterministicExtractor`
    - _Requirements: 2.1, 2.3_
  - [~] 26.3 Wire provider selection through `core/config.py`
    - Select live vs simulated data source and Groq/Gemini/deterministic LLM by configuration, keeping
      the deterministic path as the guaranteed fallback
    - _Requirements: 1.3, 2.3_
  - [ ]* 26.4 Write unit tests for live-provider fallback wiring
    - Assert a failing live data source falls back to simulated (1.3) and a failing LLM provider falls
      back to deterministic extraction (2.3)
    - _Requirements: 1.3, 2.3_

- [x] 27. Final checkpoint - ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional test sub-tasks and can be skipped for a faster MVP, but they
  implement the design's dual testing strategy (property-based + example tests).
- Property-based tests use **Hypothesis** (backend) and **fast-check** (frontend), run a minimum of
  100 iterations each, and carry the tag comment
  `# Feature: oilshield-command-center, Property {number}: {property_text}` (`//` in TypeScript).
- Each of the 23 correctness properties is implemented by exactly one property-based test:
  P1 (7.2), P2 (7.3), P3 (6.4), P4 (8.2), P5 (9.2), P6 (9.3), P7 (9.4), P8 (9.5), P9 (10.3),
  P10 (12.3), P11 (12.4), P12 (13.2), P13 (13.3), P14 (13.4), P15 (13.5), P16 (14.2), P17 (14.3),
  P18 (16.3), P19 (16.4), P20 (16.5), P21 (23.1), P22 (17.3), P23 (20.3).
- The simulated / deterministic providers are built before the live ones so the full pipeline runs
  offline early; live Groq/Gemini providers are added last behind the same abstraction.
- Bundled simulated JSON datasets double as deterministic test fixtures for reproducible demos.
- Checkpoints provide incremental validation points where the app is runnable end-to-end.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1", "2", "3.1", "3.2", "3.3", "5"] },
    { "id": 1, "tasks": ["4.1", "4.2"] },
    { "id": 2, "tasks": ["6.1", "6.2", "6.3", "6.5"] },
    { "id": 3, "tasks": ["6.4", "7.1", "8.1"] },
    { "id": 4, "tasks": ["7.2", "7.3", "7.4", "8.2", "8.3", "9.1"] },
    { "id": 5, "tasks": ["9.2", "9.3", "9.4", "9.5", "10.1", "10.2"] },
    { "id": 6, "tasks": ["10.3", "12.1"] },
    { "id": 7, "tasks": ["12.2", "13.1"] },
    { "id": 8, "tasks": ["12.3", "12.4", "13.2", "13.3", "13.4", "13.5", "13.6", "14.1"] },
    { "id": 9, "tasks": ["14.2", "14.3", "15", "16.1"] },
    { "id": 10, "tasks": ["16.2", "16.3", "16.4", "16.5", "17.1"] },
    { "id": 11, "tasks": ["17.2", "17.3", "17.4", "17.5"] },
    { "id": 12, "tasks": ["19.1", "19.2"] },
    { "id": 13, "tasks": ["19.3", "20.1", "20.2"] },
    { "id": 14, "tasks": ["20.3", "20.4", "21.1", "22.1", "23"] },
    { "id": 15, "tasks": ["21.2", "22.2", "23.1", "24.1"] },
    { "id": 16, "tasks": ["24.2"] },
    { "id": 17, "tasks": ["24.3", "26.1", "26.2"] },
    { "id": 18, "tasks": ["26.3"] },
    { "id": 19, "tasks": ["26.4"] }
  ]
}
```
