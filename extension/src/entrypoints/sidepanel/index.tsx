import React from "react";
import ReactDOM from "react-dom/client";

// import vite tailwind css
import "@/assets/tailwind.css";

import { ErrorView } from "./components/error-view";
import { InitialView } from "./components/initial-view";
import { LoadingView } from "./components/logina-view";
import { RecordingView } from "./components/recording-view";
import { StoppedView } from "./components/stopped-view";
import { WorkflowProvider, useWorkflow } from "./context/workflow-provider";

// eslint-disable-next-line react-refresh/only-export-components
const AppContent: React.FC = () => {
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

// eslint-disable-next-line react-refresh/only-export-components
const SidepanelApp: React.FC = () => {
  return (
    <React.StrictMode>
      <WorkflowProvider>
        <div className="h-screen flex flex-col">
          <main className="flex-grow overflow-auto">
            <AppContent />
          </main>
        </div>
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
