import { Play, Settings, Edit3, SidebarOpen, Terminal } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { SidebarTrigger } from '@/components/ui/sidebar';
import { useAppContext } from '@/contexts/AppContext';

export function TopToolbar() {
  const {
    setDisplayMode,
    displayMode,
    currentWorkflowData,
    setActiveDialog,
    checkForUnsavedChanges,
    workflowStatus,
  } = useAppContext();

  const handleRunWithInputs = () => {
    if (checkForUnsavedChanges()) {
      return;
    }
    console.log('Running workflow with inputs:', currentWorkflowData?.name);
    setActiveDialog('run');
  };

  const handleRunAsTool = () => {
    if (checkForUnsavedChanges()) {
      return;
    }
    console.log('Running workflow as tool:', currentWorkflowData?.name);
    setActiveDialog('runAsTool');
  };

  const handleToggleMode = () => {
    if (displayMode === 'canvas') {
      console.log('Editing workflow:', currentWorkflowData?.name);
      setDisplayMode('editor');
    } else {
      setDisplayMode('canvas');
    }
  };

  return (
    <div className="border-b border-gray-200 bg-white px-6 py-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <SidebarTrigger className="p-2">
            <SidebarOpen className="w-4 h-4" />
          </SidebarTrigger>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="lg"
            onClick={handleRunWithInputs}
            disabled={!currentWorkflowData || workflowStatus === 'running'}
            className="flex items-center gap-2 text-base px-6 py-3"
          >
            <Play className="w-5 h-5" />
            Run with Inputs
          </Button>

          <Button
            variant="outline"
            size="lg"
            onClick={handleRunAsTool}
            disabled={!currentWorkflowData || workflowStatus === 'running'}
            className="flex items-center gap-2 text-base px-6 py-3"
          >
            <Settings className="w-5 h-5" />
            Run as Tool
          </Button>

          <Button
            variant="default"
            size="lg"
            onClick={handleToggleMode}
            disabled={!currentWorkflowData}
            className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700 text-base px-6 py-3"
          >
            <Edit3 className="w-5 h-5" />
            {displayMode === 'canvas' ? 'Edit Workflow' : 'Back to Canvas'}
          </Button>
        </div>
      </div>
    </div>
  );
}
