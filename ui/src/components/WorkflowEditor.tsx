import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Trash2, Plus, GripVertical } from 'lucide-react';
import { useAppContext, WorkflowStep } from '@/contexts/AppContext';

export function WorkflowEditor() {
  const { currentWorkflowData, setCurrentWorkflowData } = useAppContext();
  const [steps, setSteps] = useState<WorkflowStep[]>([]);

  useEffect(() => {
    if (currentWorkflowData) {
      setSteps(currentWorkflowData.steps);
    }
  }, [currentWorkflowData]);

  const updateStep = (
    index: number,
    field: keyof WorkflowStep,
    value: string
  ) => {
    const updatedSteps = steps.map((step, i) =>
      i === index ? { ...step, [field]: value } : step
    );
    setSteps(updatedSteps);

    if (currentWorkflowData) {
      setCurrentWorkflowData({
        ...currentWorkflowData,
        steps: updatedSteps,
      });
    }
  };

  const addStep = () => {
    const newStep: WorkflowStep = {
      id: `step-${Date.now()}`,
      label: 'New Step',
      action: 'click',
      target: '',
      value: '',
      stepNumber: steps.length + 1,
    };
    const updatedSteps = [...steps, newStep];
    setSteps(updatedSteps);

    if (currentWorkflowData) {
      setCurrentWorkflowData({
        ...currentWorkflowData,
        steps: updatedSteps,
      });
    }
  };

  const removeStep = (index: number) => {
    const updatedSteps = steps
      .filter((_, i) => i !== index)
      .map((step, i) => ({ ...step, stepNumber: i + 1 }));
    setSteps(updatedSteps);

    if (currentWorkflowData) {
      setCurrentWorkflowData({
        ...currentWorkflowData,
        steps: updatedSteps,
      });
    }
  };

  const moveStep = (fromIndex: number, toIndex: number) => {
    const updatedSteps = [...steps];
    const [movedStep] = updatedSteps.splice(fromIndex, 1);
    updatedSteps.splice(toIndex, 0, movedStep);

    // Update step numbers
    const reorderedSteps = updatedSteps.map((step, i) => ({
      ...step,
      stepNumber: i + 1,
    }));
    setSteps(reorderedSteps);

    if (currentWorkflowData) {
      setCurrentWorkflowData({
        ...currentWorkflowData,
        steps: reorderedSteps,
      });
    }
  };

  if (!currentWorkflowData) {
    return (
      <div className="flex items-center justify-center h-full text-gray-500">
        No workflow selected for editing
      </div>
    );
  }

  return (
    <div className="p-6 h-full overflow-y-auto bg-gray-50">
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              {currentWorkflowData.name}
            </h1>
            <p className="text-gray-600">{currentWorkflowData.description}</p>
          </div>
          <Button onClick={addStep} className="flex items-center gap-2">
            <Plus className="w-4 h-4" />
            Add Step
          </Button>
        </div>

        <div className="space-y-4">
          {steps.map((step, index) => (
            <Card key={step.id} className="bg-white">
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center justify-between text-lg">
                  <div className="flex items-center gap-3">
                    <GripVertical className="w-5 h-5 text-gray-400 cursor-move" />
                    <span>Step {step.stepNumber}</span>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => removeStep(index)}
                    className="text-red-600 hover:text-red-700 hover:bg-red-50"
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor={`label-${index}`}>Label</Label>
                    <Input
                      id={`label-${index}`}
                      value={step.label}
                      onChange={(e) =>
                        updateStep(index, 'label', e.target.value)
                      }
                      placeholder="Step description"
                    />
                  </div>
                  <div>
                    <Label htmlFor={`action-${index}`}>Action</Label>
                    <Select
                      value={step.action}
                      onValueChange={(value) =>
                        updateStep(index, 'action', value)
                      }
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="navigate">Navigate</SelectItem>
                        <SelectItem value="click">Click</SelectItem>
                        <SelectItem value="type">Type</SelectItem>
                        <SelectItem value="wait">Wait</SelectItem>
                        <SelectItem value="extract">Extract</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor={`target-${index}`}>Target</Label>
                    <Input
                      id={`target-${index}`}
                      value={step.target}
                      onChange={(e) =>
                        updateStep(index, 'target', e.target.value)
                      }
                      placeholder="CSS selector or URL"
                    />
                  </div>
                  {(step.action === 'type' || step.action === 'navigate') && (
                    <div>
                      <Label htmlFor={`value-${index}`}>Value</Label>
                      <Input
                        id={`value-${index}`}
                        value={step.value || ''}
                        onChange={(e) =>
                          updateStep(index, 'value', e.target.value)
                        }
                        placeholder="Text to type or URL"
                      />
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
