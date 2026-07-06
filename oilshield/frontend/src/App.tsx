// Application root — assembles the full command center (Requirements 10.1,
// 10.4, 10.5).
//
// The DashboardShell provides the dark-mode chrome (header, global provenance
// banner, and the responsive module grid). Each region is filled with its real
// data-fetching view: the Live Risk Radar, the Disruption Scenario Simulator,
// the Adaptive Procurement recommender, and the end-to-end Pipeline runner.
//
// Every module view is self-contained — it owns its own loading indicator and
// module-scoped error surface and fetches independently — so one module failing
// renders an in-place error without blanking out its siblings (R10.4, R10.5).

import { DashboardShell, KpiStrip } from "./components";
import {
  RiskRadarView,
  ScenarioSimulatorView,
  ProcurementView,
  PipelineRunnerView,
} from "./views";

function App() {
  return (
    <DashboardShell
      // Default global provenance for the offline demo; each module also
      // surfaces its own live/simulated provenance from its fetched data (R4.4).
      dataSourceMode="simulated"
      dataSourceModes={{ news: "simulated", prices: "simulated" }}
      overview={<KpiStrip />}
      riskRadar={<RiskRadarView />}
      scenarioSimulator={<ScenarioSimulatorView />}
      procurement={<ProcurementView />}
      pipeline={<PipelineRunnerView />}
    />
  );
}

export default App;
