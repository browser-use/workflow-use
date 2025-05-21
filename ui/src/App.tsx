import { ReactFlowProvider } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import WorkflowLayout from "./components/workflow-layout";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// Create a client
const queryClient = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ReactFlowProvider>
        <WorkflowLayout />
      </ReactFlowProvider>
    </QueryClientProvider>
  );
}
