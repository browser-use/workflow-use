import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from './ui/dialog';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';
import { workflowService } from '@/services/workflowService';
import { Workflow } from '@/types/workflow-layout.types';
import { useAppContext } from '@/contexts/AppContext';
import { toast } from './ui/use-toast';
import { Clock, ListChecks, Activity } from 'lucide-react';

interface WorkflowRecordResponse {
  success: boolean;
  workflow?: Workflow;
  error?: string;
}

interface EditRecordingDialogProps {
  isOpen: boolean;
  onClose: () => void;
  recordingData: WorkflowRecordResponse;
}

interface ConfirmCloseDialogProps {
  isOpen: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

const ConfirmCloseDialog: React.FC<ConfirmCloseDialogProps> = ({
  isOpen,
  onConfirm,
  onCancel,
}) => {
  return (
    <Dialog open={isOpen} onOpenChange={onCancel}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Confirm Close</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-gray-500">
          Are you sure you want to close the workflow editor? Any unsaved
          changes will be lost.
        </p>
        <DialogFooter>
          <Button variant="outline" onClick={onCancel}>
            Continue Editing
          </Button>
          <Button variant="destructive" onClick={onConfirm}>
            Close Without Saving
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export function EditRecordingDialog({
  isOpen,
  onClose,
  recordingData,
}: EditRecordingDialogProps) {
  const [editedData, setEditedData] = useState<Workflow>({
    name: '',
    steps: [],
    description: '',
    version: '',
    workflow_analysis: '',
    input_schema: [],
  });
  const [isBuilding, setIsBuilding] = useState(false);
  const [userPrompt, setUserPrompt] = useState('');
  const [showConfirmClose, setShowConfirmClose] = useState(false);
  const { recordingStatus, setRecordingStatus, fetchWorkflows } =
    useAppContext();

  // Update editedData when recordingData changes
  useEffect(() => {
    if (recordingData?.workflow) {
      setEditedData({
        name: recordingData.workflow.name || '',
        steps: recordingData.workflow.steps || [],
        description: recordingData.workflow.description || '',
        version: recordingData.workflow.version || '',
        workflow_analysis: recordingData.workflow.workflow_analysis,
        input_schema: recordingData.workflow.input_schema || [],
      });
    }
  }, [recordingData]);

  const handleSave = async () => {
    try {
      setIsBuilding(true);
      const response = await workflowService.buildWorkflow(
        editedData.name,
        userPrompt,
        {
          ...editedData,
        }
      );
      if (response.success) {
        await fetchWorkflows();
        onClose();
        setRecordingStatus('idle');
        toast({
          title: '✨ Workflow Built Successfully',
          description: 'Your workflow has been created and is ready to use.',
        });
      } else {
        console.error('Failed to build workflow:', response.error);
        toast({
          title: '❌ Failed to Build Workflow',
          description:
            response.error || 'An error occurred while building the workflow.',
        });
      }
    } catch (error) {
      console.error('Error building workflow:', error);
      toast({
        title: '❌ Failed to Build Workflow',
        description:
          'An unexpected error occurred while building the workflow.',
      });
    } finally {
      setIsBuilding(false);
      setRecordingStatus('idle');
    }
  };

  const handleCloseAttempt = () => {
    if (recordingStatus === 'building') {
      return; // Prevent closing while building
    }
    setShowConfirmClose(true);
  };

  const handleConfirmClose = () => {
    setShowConfirmClose(false);
    onClose();
    setRecordingStatus('idle');
  };

  const handleCancelClose = () => {
    setShowConfirmClose(false);
  };

  const getStepTypeCount = () => {
    const counts: Record<string, number> = {};
    editedData.steps?.forEach((step: any) => {
      counts[step.type] = (counts[step.type] || 0) + 1;
    });
    return counts;
  };

  return (
    <>
      <Dialog
        open={isOpen}
        onOpenChange={(open) => {
          if (!open) {
            handleCloseAttempt();
          }
        }}
      >
        <DialogContent className="sm:max-w-7xl max-h-[90vh] p-10">
          <DialogHeader>
            <DialogTitle className="text-2xl font-bold">
              Edit Recorded Workflow
            </DialogTitle>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-8 h-full overflow-hidden">
            {/* Left side - Prompt and Workflow Info */}
            <div className="flex flex-col gap-4 h-full overflow-y-auto flex-1 min-h-0">
              <div className="grid gap-4 p-4">
                <div className="grid gap-2">
                  <h3 className="text-lg font-semibold">Workflow Name</h3>
                  <input
                    id="name"
                    value={editedData.name}
                    onChange={(e) =>
                      setEditedData({ ...editedData, name: e.target.value })
                    }
                    className="border rounded-md p-5 text-lg"
                  />
                </div>

                <div className="grid gap-2">
                  <h3 className="text-lg font-semibold">
                    Describe what this workflow should do
                  </h3>
                  <Textarea
                    id="prompt"
                    value={userPrompt}
                    onChange={(e) => setUserPrompt(e.target.value)}
                    placeholder="Describe the purpose and behavior of this workflow. The AI will use this to optimize the steps..."
                    className="min-h-[300px] text-lg ml-1 focus:outline-black focus:outline-2 p-5"
                  />
                </div>
              </div>
            </div>

            {/* Right side - Statistics Summary */}
            <div className="flex flex-col gap-6">
              <div className="grid grid-cols-3 gap-4">
                <div className="bg-purple-50 p-6 rounded-xl border border-purple-100">
                  <div className="flex items-center gap-3">
                    <ListChecks className="h-6 w-6 text-purple-600" />
                    <div>
                      <p className="text-sm text-purple-600 font-medium">
                        Total Steps
                      </p>
                      <p className="text-2xl font-bold">
                        {editedData.steps?.length || 0}
                      </p>
                    </div>
                  </div>
                </div>
                <div className="bg-blue-50 p-6 rounded-xl border border-blue-100">
                  <div className="flex items-center gap-3">
                    <Activity className="h-6 w-6 text-blue-600" />
                    <div>
                      <p className="text-sm text-blue-600 font-medium">
                        Step Types
                      </p>
                      <p className="text-2xl font-bold">
                        {Object.keys(getStepTypeCount()).length}
                      </p>
                    </div>
                  </div>
                </div>
                <div className="bg-green-50 p-6 rounded-xl border border-green-100">
                  <div className="flex items-center gap-3">
                    <Clock className="h-6 w-6 text-green-600" />
                    <div>
                      <p className="text-sm text-green-600 font-medium">
                        Recording Time
                      </p>
                      <p className="text-2xl font-bold">
                        {new Date().toLocaleTimeString()}
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              <div className="bg-white p-6 rounded-xl border">
                <h3 className="text-lg font-semibold mb-4">
                  Step Type Distribution
                </h3>
                <div className="space-y-3">
                  {Object.entries(getStepTypeCount()).map(([type, count]) => (
                    <div
                      key={type}
                      className="flex items-center justify-between"
                    >
                      <span className="text-gray-600">{type}</span>
                      <span className="font-medium">{count}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <DialogFooter className="mt-6">
            <Button
              variant="outline"
              onClick={handleCloseAttempt}
              disabled={recordingStatus === 'building'}
            >
              Cancel
            </Button>
            <Button
              onClick={handleSave}
              disabled={isBuilding || !userPrompt.trim()}
              className="bg-purple-600 hover:bg-purple-700"
            >
              {isBuilding ? 'Building...' : 'Build Workflow'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmCloseDialog
        isOpen={showConfirmClose}
        onConfirm={handleConfirmClose}
        onCancel={handleCancelClose}
      />
    </>
  );
}
