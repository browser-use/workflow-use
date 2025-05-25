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
  label: string;
  type: 'text' | 'url' | 'selector';
  placeholder: string;
  value: string;
}

export function RunWorkflowDialog() {
  const {
    executeWorkflow,
    showRunDialog,
    setShowRunDialog,
    currentWorkflowData,
  } = useAppContext();
  const [inputs, setInputs] = useState<WorkflowInput[]>([]);
  const [isExecuting, setIsExecuting] = useState(false);

  useEffect(() => {
    if (currentWorkflowData && showRunDialog) {
      // Extract dynamic inputs from workflow steps - only fields with {} around them
      const dynamicInputs: WorkflowInput[] = [];

      currentWorkflowData.steps.forEach((step, index) => {
        if (
          step.type === 'navigation' &&
          step.url &&
          step.url.includes('{') &&
          step.url.includes('}')
        ) {
          dynamicInputs.push({
            id: `navigate-${index}`,
            label: `URL for "${step.description}"`,
            type: 'url',
            placeholder: step.url,
            value: '', // Empty by default
          });
        }
        if (
          step.type === 'input' &&
          step.value &&
          step.value.includes('{') &&
          step.value.includes('}')
        ) {
          dynamicInputs.push({
            id: `input-${index}`,
            label: `Input for "${step.description}"`,
            type: 'text',
            placeholder: step.value,
            value: '', // Empty by default
          });
        }
        if (
          step.type === 'agent' &&
          step.task &&
          step.task.includes('{') &&
          step.task.includes('}')
        ) {
          dynamicInputs.push({
            id: `selector-${index}`,
            label: `Task for "${step.description}"`,
            type: 'selector',
            placeholder: step.task,
            value: '', // Empty by default
          });
        }
      });

      setInputs(dynamicInputs);
    }
  }, [currentWorkflowData, showRunDialog]);

  const updateInput = (id: string, value: string) => {
    setInputs(
      inputs.map((input) => (input.id === id ? { ...input, value } : input))
    );
  };

  const execute = async () => {
    setIsExecuting(true);
    console.log('Executing workflow with inputs:', inputs);

    const inputFields = inputs.map((input) => ({
      name: input.placeholder.replace(/[{}]/g, ''),
      type: input.type,
      required: true, // all dynamic inputs assumed required
      value: input.value,
    }));

    await executeWorkflow(currentWorkflowData.name, inputFields);

    setIsExecuting(false);
    setShowRunDialog(false);
  };

  if (!currentWorkflowData) return null;

  return (
    <Dialog open={showRunDialog} onOpenChange={setShowRunDialog}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
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
                  {input.label}
                </Label>
                <Input
                  id={input.id}
                  value={input.value}
                  onChange={(e) => updateInput(input.id, e.target.value)}
                  placeholder={input.placeholder}
                  className="w-full"
                />
              </div>
            ))}

            {inputs.length === 0 && (
              <p className="text-gray-500 text-center py-8">
                This workflow doesn't require any input parameters.
              </p>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => setShowRunDialog(false)}
            disabled={isExecuting}
          >
            Cancel
          </Button>
          <Button
            onClick={execute}
            disabled={isExecuting}
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
