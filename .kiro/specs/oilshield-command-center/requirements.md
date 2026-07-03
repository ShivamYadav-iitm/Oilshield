# Requirements Document

## Introduction

OilShield is an Integrated Resilience Command Center delivered as a single web dashboard for the theme "AI-Driven Energy Supply Chain Resilience for Import-Dependent Economies," focused on India's crude oil supply chain. The product demonstrates an end-to-end "signal to recommendation" pipeline through three connected modules presented in one modern dark-mode dashboard:

1. **Live Risk Radar** — ingests news, sanctions, and shipping signals and computes a live supply-disruption risk score per shipping corridor and per supplier country, using an LLM/RAG step to extract risk signals from unstructured news text.
2. **Disruption Scenario Simulator** — lets a user run "what-if" scenarios (for example, Strait of Hormuz partial closure, OPEC+ production cut, Red Sea shutdown) and computes cascading impacts on refinery run rates, domestic fuel prices, strategic petroleum reserve (SPR) days-of-cover, and GDP trajectory, using explicit and testable assumptions.
3. **Adaptive Procurement Recommendation** — an agentic engine that identifies and ranks alternative crude sources and tanker routes, factoring spot price, tanker availability, port congestion, and refinery grade compatibility, producing actionable procurement recommendations.

This is a hackathon MVP built by a beginner programmer with heavy AI assistance, so scope is intentionally bounded: real free data feeds are used where practical, and realistic simulated data is used as a documented fallback. The requirements below prioritize a working, demonstrable end-to-end flow that maps to the judging criteria (Innovation, Business Impact, Technical Excellence, Scalability, User Experience).

## Glossary

- **OilShield**: The complete web application, including all three modules and the dashboard shell.
- **Dashboard**: The single-page web interface that presents all modules, the map, charts, risk indicators, and the timeline.
- **Signal_Ingestion_Service**: The backend component that retrieves raw signals from external feeds or simulated data sources and normalizes them into a common internal record format.
- **Signal**: A normalized record derived from a news item, sanctions notice, or shipping event, containing at minimum a source, timestamp, text summary, affected corridor or supplier country, and a raw severity indicator.
- **Risk_Radar**: The module that displays current risk levels across corridors and supplier countries.
- **Risk_Scoring_Engine**: The backend component that converts extracted signals into a numeric supply-disruption risk score.
- **Risk_Score**: A numeric value between 0 and 100 inclusive representing supply-disruption probability for a given corridor or supplier country, where higher values indicate higher risk.
- **Corridor**: A named maritime shipping route relevant to India's crude imports (for example, Strait of Hormuz, Red Sea, Cape of Good Hope).
- **Supplier_Country**: A named crude oil exporting country relevant to India's imports (for example, Iraq, Saudi Arabia, Russia, United States).
- **LLM_Extractor**: The component that uses a large language model with retrieval-augmented generation to extract structured risk signals from unstructured signal text.
- **Scenario_Simulator**: The module that runs disruption what-if scenarios and computes cascading impacts.
- **Scenario**: A named disruption configuration with explicit input assumptions (for example, corridor closure percentage, production cut volume, duration in days).
- **Scenario_Assumption**: A single named, numeric or categorical input parameter of a Scenario that is displayed to the user and used by the computation.
- **Impact_Result**: The set of computed outputs of a Scenario, including refinery run rate change, domestic fuel price change, SPR days-of-cover, and GDP trajectory change.
- **SPR**: Strategic Petroleum Reserve, the stored crude oil buffer measured in days-of-cover.
- **Procurement_Recommender**: The module that ranks alternative crude sources and tanker routes.
- **Procurement_Option**: A candidate combination of a Supplier_Country crude grade and a tanker route, with attributes for spot price, tanker availability, port congestion, and refinery grade compatibility.
- **Recommendation_Score**: A numeric value used to rank Procurement_Options, computed from the option attributes.
- **Data_Source_Mode**: A per-feed flag indicating whether data is "live" (from an external feed) or "simulated" (from bundled realistic data).
- **Pipeline_Latency**: The elapsed wall-clock time from the moment a user initiates the end-to-end flow to the moment a ranked procurement recommendation is displayed.

## Requirements

### Requirement 1: Signal Ingestion and Normalization

**User Story:** As a supply chain analyst, I want the system to collect and normalize risk signals from external and simulated sources, so that all downstream analysis works from a consistent data set.

#### Acceptance Criteria

1. WHEN the Signal_Ingestion_Service runs a data refresh, THE Signal_Ingestion_Service SHALL retrieve raw signals from each configured data source.
2. WHEN a raw signal is retrieved, THE Signal_Ingestion_Service SHALL normalize the raw signal into a Signal record containing a source, a timestamp, a text summary, an affected Corridor or Supplier_Country, and a raw severity indicator.
3. IF an external data source is unreachable or returns an error, THEN THE Signal_Ingestion_Service SHALL fall back to bundled simulated data for that source and set Data_Source_Mode to "simulated" for that source.
4. IF a raw signal contains malformed data that cannot be normalized into a Signal record, THEN THE Signal_Ingestion_Service SHALL fail the current data refresh and report the malformed signal.
5. WHERE a data source is configured as simulated, THE Signal_Ingestion_Service SHALL load Signal records from bundled data files.
6. THE Signal_Ingestion_Service SHALL record the Data_Source_Mode value for each data source so that the Dashboard can display data provenance.

### Requirement 2: LLM/RAG Risk Signal Extraction

**User Story:** As a supply chain analyst, I want the system to extract structured risk information from unstructured news text, so that I can understand risk drivers without reading every article.

#### Acceptance Criteria

1. WHEN a Signal with text content is processed, THE LLM_Extractor SHALL produce a structured output containing an affected Corridor or Supplier_Country, a risk category, and a severity value between 0 and 100 inclusive.
2. IF the LLM_Extractor cannot map a Signal to a known Corridor or Supplier_Country for any reason, THEN THE LLM_Extractor SHALL label the Signal as "unclassified", and THE Risk_Scoring_Engine SHALL exclude every unclassified Signal from Risk_Score computation.
3. IF a call to the language model fails or times out, THEN THE LLM_Extractor SHALL return a fallback structured output using the raw severity indicator from the Signal record.
4. THE LLM_Extractor SHALL attach the originating Signal source and timestamp to each structured output so that risk drivers remain traceable to evidence.

### Requirement 3: Live Risk Scoring

**User Story:** As a supply chain analyst, I want a live risk score for each corridor and supplier country, so that I can see where disruption risk is concentrated.

#### Acceptance Criteria

1. WHEN structured signal outputs are available, THE Risk_Scoring_Engine SHALL compute a Risk_Score for each Corridor and each Supplier_Country.
2. THE Risk_Scoring_Engine SHALL produce every Risk_Score as a value between 0 and 100 inclusive.
3. WHEN no signals are available for a Corridor or Supplier_Country, THE Risk_Scoring_Engine SHALL assign that Corridor or Supplier_Country a Risk_Score of 0.
4. THE Risk_Scoring_Engine SHALL classify each Risk_Score into a status band of "low" for scores from 0 to 33, "elevated" for scores from 34 to 66, and "high" for scores from 67 to 100.
5. WHEN a new data refresh completes, THE Risk_Radar SHALL display the updated Risk_Score and status band for each Corridor and Supplier_Country.

### Requirement 4: Risk Radar Presentation

**User Story:** As a decision maker, I want to see current risks on a map and in a list, so that I can quickly grasp the situation.

#### Acceptance Criteria

1. THE Risk_Radar SHALL display each Corridor on the map with a color that corresponds to the Corridor status band.
2. THE Risk_Radar SHALL display a ranked list of Corridors and Supplier_Countries ordered by Risk_Score from highest to lowest.
3. WHEN a user selects a Corridor or Supplier_Country, THE Risk_Radar SHALL display the contributing Signals with their source and timestamp.
4. THE Risk_Radar SHALL display the Data_Source_Mode for the underlying signals so that a viewer can distinguish live data from simulated data.

### Requirement 5: Disruption Scenario Configuration

**User Story:** As an energy planner, I want to configure and run predefined disruption scenarios, so that I can explore the impact of specific events.

#### Acceptance Criteria

1. THE Scenario_Simulator SHALL provide a set of predefined Scenarios including at minimum a Strait of Hormuz partial closure, an OPEC+ production cut, and a Red Sea shutdown.
2. WHEN a user selects a Scenario, THE Scenario_Simulator SHALL display all Scenario_Assumptions with their current values before the Scenario is run.
3. WHERE a Scenario_Assumption is marked adjustable, THE Scenario_Simulator SHALL allow the user to change the value within a defined valid range.
4. WHERE a Scenario_Assumption is marked adjustable, WHEN a user submits a value within the defined valid range for that Scenario_Assumption, THE Scenario_Simulator SHALL apply the submitted value as the current value of that Scenario_Assumption.
5. IF a user submits a Scenario_Assumption value outside its defined valid range or otherwise invalid, THEN THE Scenario_Simulator SHALL reject the submitted value before the submitted value takes effect, retain the previous valid value as the current value of that Scenario_Assumption, and display the valid range to the user.

### Requirement 6: Scenario Impact Computation

**User Story:** As an energy planner, I want the system to compute cascading impacts from a scenario, so that I can understand downstream consequences.

#### Acceptance Criteria

1. WHEN a user runs a Scenario, THE Scenario_Simulator SHALL compute an Impact_Result containing a refinery run rate change, a domestic fuel price change, an SPR days-of-cover value, and a GDP trajectory change.
2. THE Scenario_Simulator SHALL display the Scenario_Assumptions used for each Impact_Result alongside the results.
3. WHEN a Scenario increases the closure percentage of a Corridor, THE Scenario_Simulator SHALL produce an SPR days-of-cover value that is less than or equal to the value produced for a lower closure percentage with all other assumptions unchanged.
4. THE Scenario_Simulator SHALL constrain the SPR days-of-cover value to be greater than or equal to 0.
5. THE Scenario_Simulator SHALL compute each Impact_Result within 5 seconds of the user running the Scenario.
6. THE Scenario_Simulator SHALL display the Impact_Result as a timeline showing projected values over the Scenario duration.

### Requirement 7: Scenario Save and Restore

**User Story:** As an energy planner, I want to save a configured scenario and reload it, so that I can reproduce and share results during a demo.

#### Acceptance Criteria

1. WHEN a user saves a Scenario, THE Scenario_Simulator SHALL serialize the Scenario name and all Scenario_Assumption values into a stored representation.
2. WHEN a user loads a saved Scenario, THE Scenario_Simulator SHALL deserialize the stored representation into a Scenario with identical Scenario_Assumption values to those that were saved (round-trip property).
3. IF a stored Scenario representation is malformed, is incompatible with the current Scenario version, or fails to deserialize for any reason, THEN THE Scenario_Simulator SHALL reject the load and display a descriptive error.

### Requirement 8: Adaptive Procurement Recommendation

**User Story:** As a procurement officer, I want ranked alternative crude sources and routes, so that I can respond to a disruption with concrete actions.

#### Acceptance Criteria

1. WHEN a user requests procurement recommendations, THE Procurement_Recommender SHALL generate a set of Procurement_Options, each combining a Supplier_Country crude grade and a tanker route.
2. THE Procurement_Recommender SHALL compute a Recommendation_Score for each Procurement_Option from spot price, tanker availability, port congestion, and refinery grade compatibility.
3. IF a Procurement_Option has a refinery grade compatibility below the defined minimum threshold, THEN THE Procurement_Recommender SHALL exclude that Procurement_Option from the recommended set.
4. THE Procurement_Recommender SHALL display Procurement_Options ordered by Recommendation_Score from highest to lowest.
5. THE Procurement_Recommender SHALL display, for each recommended Procurement_Option, the spot price, tanker availability, port congestion, refinery grade compatibility, and a plain-language rationale.

### Requirement 9: End-to-End Signal-to-Recommendation Pipeline

**User Story:** As a hackathon judge, I want to see the full flow from live signal to procurement recommendation, so that I can evaluate response time and integration.

#### Acceptance Criteria

1. WHEN a user initiates the end-to-end flow, THE OilShield SHALL execute signal ingestion, risk scoring, scenario impact computation, and procurement recommendation in sequence and display each stage result.
2. THE OilShield SHALL display the Pipeline_Latency for a completed end-to-end flow.
3. WHEN a corridor Risk_Score enters the "high" status band, THE OilShield SHALL surface a recommended Scenario and a procurement action linked to that Corridor.
4. THE OilShield SHALL complete the end-to-end flow within 15 seconds when all data sources are in simulated mode.

### Requirement 10: Dashboard and User Experience

**User Story:** As a user, I want a modern, readable command center interface, so that I can understand and present the analysis clearly.

#### Acceptance Criteria

1. THE Dashboard SHALL present the Risk_Radar, Scenario_Simulator, and Procurement_Recommender within a single dark-mode interface.
2. THE Dashboard SHALL display a map showing Corridors and tanker routes, charts for Impact_Results, and status badges for Risk_Scores.
3. THE Dashboard SHALL display a timeline component that shows Signal events and Scenario projections in chronological order.
4. WHILE a backend computation is in progress and has not failed, THE Dashboard SHALL display a loading indicator for the affected module.
5. IF a backend computation fails, THEN THE Dashboard SHALL display an error message that identifies the affected module, replace any loading indicator for that module with the error message, and preserve previously displayed results for other modules.
