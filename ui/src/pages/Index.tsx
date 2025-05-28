import { useState } from 'react';
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
import { Loader2, Terminal } from 'lucide-react';

const Index2 = () => {
  const { displayMode, workflowStatus } = useAppContext();
  const [showLogViewer, setShowLogViewer] = useState(false);
  const toggleLogViewer = () => setShowLogViewer((prev) => !prev);

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full bg-gray-50">
        {/* Sidebar */}
        <div className="w-1/4 max-w-sm bg-white border-r border-gray-200">
          <WorkflowSidebar />
        </div>

        {/* Main Content Area */}
        <div className="flex-1 flex flex-col">
          <TopToolbar />

          <div className="flex-1 flex flex-col overflow-hidden">
            {displayMode === 'start' ? (
              <Welcome />
            ) : displayMode === 'canvas' ? (
              <div className="flex-1 flex flex-col overflow-hidden">
                {/* Main canvas area */}
                <div className="relative flex-1 overflow-auto">
                  <WorkflowCanvas />
                  {/* Toggle button - always visible, moves with LogViewer */}
                  <div
                    className={`absolute left-1/2 -translate-x-1/2  ${
                      showLogViewer ? 'bottom-3' : 'bottom-10'
                    }`}
                  >
                    <button
                      onClick={toggleLogViewer}
                      className={`${
                        workflowStatus === 'running'
                          ? 'bg-green-700 hover:bg-green-500'
                          : 'bg-gray-500 hover:bg-gray-600'
                      } text-white rounded-full px-4 py-2 shadow flex items-center`}
                      title="Toggle Terminal"
                    >
                      <div className="bg-white bg-opacity-20 rounded-full p-2 flex items-center justify-center">
                        {workflowStatus === 'running' ? (
                          <Loader2 className="w-5 h-5 animate-spin" />
                        ) : (
                          <Terminal className="w-5 h-5" />
                        )}
                      </div>
                      <p className="ml-3 mb-0">Toggle Terminal</p>
                    </button>
                  </div>
                </div>

                {/* Log view area at the bottom, like a terminal */}
                <div
                  className={`${
                    showLogViewer ? 'block' : 'hidden'
                  } h-1/3 border-t border-gray-200 overflow-auto transform transition-transform duration-300 ease-in-out translate-y-0`}
                >
                  <LogViewer />
                </div>
              </div>
            ) : displayMode === 'editor' ? (
              <WorkflowEditor />
            ) : (
              <WorkflowCanvas />
            )}
          </div>
        </div>

        {/* Dialogs */}
        <RunWorkflowDialog />
        <RunAsToolDialog />
      </div>
    </SidebarProvider>
  );
};

export default Index2;
