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
import { Trash2 } from 'lucide-react';
import { Workflow } from '@/types/workflow-layout.types';
import { useAppContext } from '@/contexts/AppContext';

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
  const { recordingStatus, setRecordingStatus } = useAppContext();

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
      console.log('BUILD WORKFLOW RESPONSE', response);
      if (response.success) {
        onClose();
        setRecordingStatus('idle');
      } else {
        console.error('Failed to build workflow:', response.error);
      }
    } catch (error) {
      console.error('Error building workflow:', error);
    } finally {
      setIsBuilding(false);
      setRecordingStatus('idle');
    }
  };

  const handleDeleteStep = (index: number) => {
    const newSteps = [...editedData.steps];
    newSteps.splice(index, 1);
    setEditedData({ ...editedData, steps: newSteps });
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
        <DialogContent className="sm:max-w-[90vw] h-[90vh]">
          <DialogHeader>
            <DialogTitle className="text-2xl font-bold">
              Edit Recorded Workflow
            </DialogTitle>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-6 h-full overflow-hidden">
            {/* Left side - Prompt and Workflow Info */}
            <div className="flex flex-col gap-6 h-full overflow-y-auto pr-4">
              <div className="grid gap-4">
                <div className="grid gap-2">
                  <label htmlFor="name" className="text-sm font-medium">
                    Workflow Name
                  </label>
                  <input
                    id="name"
                    value={editedData.name}
                    onChange={(e) =>
                      setEditedData({ ...editedData, name: e.target.value })
                    }
                    className="border rounded-md p-2 text-lg"
                  />
                </div>

                <div className="grid gap-2">
                  <label
                    htmlFor="prompt"
                    className="text-sm font-medium z-10000"
                  >
                    Describe what this workflow should do
                  </label>
                  <Textarea
                    id="prompt"
                    value={userPrompt}
                    onChange={(e) => setUserPrompt(e.target.value)}
                    placeholder="Describe the purpose and behavior of this workflow. The AI will use this to optimize the steps..."
                    className="min-h-[200px] text-lg"
                  />
                </div>
              </div>
            </div>

            {/* Right side - Steps List */}
            <div className="flex flex-col gap-4 h-full overflow-y-auto">
              <h3 className="text-lg font-semibold">Recorded Steps</h3>
              <div className="space-y-4">
                {editedData.steps?.map((step: any, index: number) => (
                  <div
                    key={index}
                    className="flex items-start gap-4 p-4 border rounded-lg bg-gray-50"
                  >
                    <div className="flex-1">
                      <div className="font-medium">{step.type}</div>
                      <div className="text-sm text-gray-600 mt-1">
                        {step.description || JSON.stringify(step, null, 2)}
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleDeleteStep(index)}
                      className="text-red-500 hover:text-red-700 hover:bg-red-50"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
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
