import React, { useCallback, useEffect, useState } from "react";
import ReactDOM from "react-dom/client";

// import vite tailwind css
import "@/assets/tailwind.css";

import { DashboardView } from "./components/dashboard-view";
import { ErrorView } from "./components/error-view";
import { InitialView } from "./components/initial-view";
import { LoadingView } from "./components/logina-view";
import { RecordingView } from "./components/recording-view";
import { SettingsView } from "./components/settings-view";
import { StoppedView } from "./components/stopped-view";
import { TabNavigation, TabId } from "./components/tab-navigation";
import { WorkflowProvider, useWorkflow } from "./context/workflow-provider";

// Record tab content — shows the appropriate view based on recording state
// eslint-disable-next-line react-refresh/only-export-components
const RecordTabContent: React.FC = () => {
  const { recordingStatus, isLoading, error } = useWorkflow();

  if (isLoading) {
    return <LoadingView />;
  }

  if (error) {
    return <ErrorView />;
  }

  switch (recordingStatus) {
    case "recording":
      return <RecordingView />;
    case "stopped":
      return <StoppedView />;
    case "idle":
    default:
      return <InitialView />;
  }
};

// Main app with tab navigation
// eslint-disable-next-line react-refresh/only-export-components
const AppContent: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabId>("record");
  const [backendConnected, setBackendConnected] = useState(false);

  // Check backend health on mount and periodically
  const checkHealth = useCallback(async () => {
    try {
      const response = await chrome.runtime.sendMessage({
        type: "CHECK_BACKEND_HEALTH",
      });
      setBackendConnected(response?.connected ?? false);
    } catch {
      setBackendConnected(false);
    }
  }, []);

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 15000); // Check every 15s
    return () => clearInterval(interval);
  }, [checkHealth]);

  const renderTabContent = () => {
    switch (activeTab) {
      case "dashboard":
        return <DashboardView />;
      case "record":
        return <RecordTabContent />;
      case "settings":
        return <SettingsView />;
      default:
        return <RecordTabContent />;
    }
  };

  return (
    <div className="h-screen flex flex-col">
      <TabNavigation
        activeTab={activeTab}
        onTabChange={setActiveTab}
        backendConnected={backendConnected}
      />
      <main className="flex-grow overflow-auto">
        {renderTabContent()}
      </main>
    </div>
  );
};

// eslint-disable-next-line react-refresh/only-export-components
const SidepanelApp: React.FC = () => {
  return (
    <React.StrictMode>
      <WorkflowProvider>
        <AppContent />
      </WorkflowProvider>
    </React.StrictMode>
  );
};

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("Root element not found");
}

const root = ReactDOM.createRoot(rootElement);
root.render(<SidepanelApp />);
