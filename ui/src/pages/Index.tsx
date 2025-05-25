import React, { useEffect } from 'react';
import { SidebarProvider } from '@/components/ui/sidebar';
import { WorkflowSidebar } from '@/components/WorkflowSidebar';
import { WorkflowCanvas } from '@/components/WorkflowCanvas';
import { WorkflowEditor } from '@/components/WorkflowEditor';
import { RunWorkflowDialog } from '@/components/RunWorkflowDialog';
import { RunAsToolDialog } from '@/components/RunAsToolDialog';
import { TopToolbar } from '@/components/TopToolbar';
import { useAppContext } from '@/contexts/AppContext';
import { LogViewer } from '@/components/LogViewer';

const Index = () => {
  const { displayMode, currentTaskId, setDisplayMode } = useAppContext();

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full bg-gray-50">
        <WorkflowSidebar />
        <main className="flex-1 flex flex-col">
          <TopToolbar />
          <div className="flex-1">
            {displayMode === 'canvas' ? (
              <WorkflowCanvas />
            ) : displayMode === 'log' ? (
              <LogViewer
                taskId={currentTaskId}
                onClose={() => setDisplayMode('canvas')}
              />
            ) : (
              <WorkflowEditor />
            )}
          </div>
        </main>
        <RunWorkflowDialog />
        <RunAsToolDialog />
      </div>
    </SidebarProvider>
  );
};

export default Index;
