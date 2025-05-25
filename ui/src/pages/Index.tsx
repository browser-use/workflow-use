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
import { Welcome } from '@/components/Welcome';

const Index = () => {
  const { displayMode, setDisplayMode } = useAppContext();

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full bg-gray-50">
        <WorkflowSidebar />
        <main className="flex-1 flex flex-col">
          <TopToolbar />
          <div className="flex-1">
            {displayMode === 'start' ? (
              <Welcome />
            ) : displayMode === 'canvas' ? (
              <WorkflowCanvas />
            ) : displayMode === 'log' ? (
              <LogViewer onClose={() => setDisplayMode('canvas')} />
            ) : displayMode === 'editor' ? (
              <WorkflowEditor />
            ) : (
              <WorkflowCanvas />
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
