import { ReactFlowProvider } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import WorkflowLayout from './components/workflow-layout';

export default function App() {
  return (
    <ReactFlowProvider>
      <WorkflowLayout />
    </ReactFlowProvider>
  );
}
