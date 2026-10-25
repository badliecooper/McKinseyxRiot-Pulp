import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { Layout } from "./components/Layout";
import { ControlTower } from "./pages/ControlTower";
import { DepotExplorer } from "./pages/DepotExplorer";
import { ScenarioReplay } from "./pages/ScenarioReplay";
import { AICopilot } from "./pages/AICopilot";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      staleTime: 30000,
    },
  },
});

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Navigate to="/control-tower" replace />} />
            <Route path="control-tower" element={<ControlTower />} />
            <Route path="depot-explorer" element={<DepotExplorer />} />
            <Route path="scenario-replay" element={<ScenarioReplay />} />
            <Route path="ai-copilot" element={<AICopilot />} />
            <Route path="*" element={<Navigate to="/control-tower" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
};

export default App;
