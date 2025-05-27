import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useAppContext } from '@/contexts/AppContext';
import { Play, Loader2 } from 'lucide-react';

interface WorkflowInput {
  id: string;
  name: string;
  type: string;
  required: boolean;
  value: string;
}

export function RunWorkflowDialog() {
  const {
    executeWorkflow,
    activeDialog,
    setActiveDialog,
    currentWorkflowData,
  } = useAppContext();
  const [inputs, setInputs] = useState<WorkflowInput[]>([]);
  const [isExecuting, setIsExecuting] = useState(false);

  useEffect(() => {
    if (currentWorkflowData && activeDialog === 'run') {
      // Use input_schema from the workflow
      const schemaInputs: WorkflowInput[] =
        currentWorkflowData.input_schema.map((input) => ({
          id: input.name,
          name: input.name,
          type: input.type,
          required: input.required,
          value: '',
        }));
      setInputs(schemaInputs);
    }
  }, [currentWorkflowData, activeDialog]);

  const updateInput = (id: string, value: string) => {
    setInputs(
      inputs.map((input) => (input.id === id ? { ...input, value } : input))
    );
  };

  const execute = async () => {
    setIsExecuting(true);
    console.log('Executing workflow with inputs:', inputs);

    // Map the input values to their corresponding places in the workflow
    const inputFields = inputs.map((input) => ({
      name: input.name,
      type: input.type,
      required: input.required,
      value: input.value,
    }));

    await executeWorkflow(currentWorkflowData.name, inputFields);

    setIsExecuting(false);
    setActiveDialog(null);
  };

  if (!currentWorkflowData) return null;

  return (
    <Dialog
      open={activeDialog === 'run'}
      onOpenChange={(open) => setActiveDialog(open ? 'run' : null)}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="text-xl font-semibold">
            Run Workflow: {currentWorkflowData.name}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-6 py-4">
          <p className="text-gray-600">
            Configure the input values for this workflow execution:
          </p>

          <div className="space-y-4">
            {inputs.map((input) => (
              <div key={input.id} className="space-y-2">
                <Label htmlFor={input.id} className="text-sm font-medium">
                  {input.name}{' '}
                  {input.required && <span className="text-red-500">*</span>}
                </Label>
                <Input
                  id={input.id}
                  value={input.value}
                  onChange={(e) => updateInput(input.id, e.target.value)}
                  placeholder={`Enter ${input.name}`}
                  className="w-full"
                  required={input.required}
                />
              </div>
            ))}

            {inputs.length === 0 && (
              <p className="text-gray-500 text-center py-8">
                This workflow doesn't require any input parameters.
              </p>
            )}
          </div>
          <p className="text-gray-500 text-sm">
            Fields marked with <span className="text-red-500">*</span> are
            required.
          </p>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => setActiveDialog(null)}
            disabled={isExecuting}
          >
            Cancel
          </Button>
          <Button
            onClick={execute}
            disabled={
              isExecuting ||
              inputs.some((input) => input.required && !input.value)
            }
            className="bg-purple-600 hover:bg-purple-700 text-white flex items-center gap-2"
          >
            {isExecuting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Executing...
              </>
            ) : (
              <>
                <Play className="w-4 h-4" />
                Execute Workflow
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
