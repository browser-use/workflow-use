import React, { useEffect, useState } from 'react';
import { z } from 'zod';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '@/components/ui/select';
import { Plus, Trash2, GripVertical } from 'lucide-react';
import { useAppContext } from '@/contexts/AppContext';
import { workflowSchema, stepSchema } from '@/types/workflow-layout.types';

type Workflow = z.infer<typeof workflowSchema>;
type Step = z.infer<typeof stepSchema>;

export function WorkflowEditor() {
  const { currentWorkflowData, updateWorkflow } = useAppContext();
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [oldWorkflow, setOldWorkflow] = useState<Workflow | null>(null);

  useEffect(() => {
    if (currentWorkflowData) {
      const safeWorkflow = workflowSchema.safeParse(currentWorkflowData);
      if (safeWorkflow.success) {
        setWorkflow(safeWorkflow.data);
        setOldWorkflow(safeWorkflow.data);
      } else console.error('Invalid workflow data', safeWorkflow.error);
    }
  }, [currentWorkflowData]);

  const updateField = (key: keyof Workflow, value: any) => {
    setWorkflow((prev) => (prev ? { ...prev, [key]: value } : prev));
  };

  const updateStepField = (index: number, key: keyof Step, value: any) => {
    if (!workflow) return;
    const newSteps = [...workflow.steps];
    newSteps[index] = { ...newSteps[index], [key]: value };
    setWorkflow({ ...workflow, steps: newSteps });
    console.log('updateStepField', index, key, value);
  };

  const addStep = () => {
    if (!workflow) return;
    const newStep: Step = stepSchema.parse({
      description: 'New step',
      type: 'click',
      timestamp: null,
      tabId: null,
    });
    setWorkflow({ ...workflow, steps: [...workflow.steps, newStep] });
    console.log('addStep');
  };

  const deleteStep = (index: number) => {
    if (!workflow) return;
    const updated = workflow.steps.filter((_, i) => i !== index);
    setWorkflow({ ...workflow, steps: updated });
    console.log('deleteStep', index);
  };

  const saveChanges = async () => {
    if (!workflow || !oldWorkflow) return;
    const validation = workflowSchema.safeParse(workflow);
    if (!validation.success)
      return console.error('Invalid workflow', validation.error);
    await updateWorkflow(oldWorkflow, validation.data);
    console.log('saveChanges', validation.data);
  };

  if (!workflow)
    return <div className="p-8 text-gray-500">No workflow loaded</div>;

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div className="space-y-2">
        <h2 className="text-xl font-semibold mb-3">Workflow Details</h2>
        <Label>Workflow Name</Label>
        <Input
          value={workflow.name}
          onChange={(e) => updateField('name', e.target.value)}
        />
        <Label>Description</Label>
        <Textarea
          value={workflow.description}
          onChange={(e) => updateField('description', e.target.value)}
          className="min-h-[100px] resize-y"
        />
        <Label>Analysis</Label>
        <Textarea
          value={workflow.workflow_analysis}
          onChange={(e) => updateField('workflow_analysis', e.target.value)}
          className="min-h-[150px] resize-y"
        />
      </div>

      <div className="flex justify-between items-center">
        <h2 className="text-xl font-semibold">Steps</h2>
        <Button onClick={addStep}>
          <Plus className="w-4 h-4 mr-1" />
          Add Step
        </Button>
      </div>

      {workflow.steps.map((step, index) => (
        <Card key={index} className="bg-white">
          <CardHeader className="pb-2">
            <CardTitle className="flex justify-between items-center">
              <span className="flex gap-2 items-center">
                <GripVertical className="w-4 h-4 text-gray-400" />
                Step {index + 1}
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => deleteStep(index)}
                className="text-red-600 hover:text-red-700"
              >
                <Trash2 className="w-4 h-4" />
              </Button>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {Object.keys(step).map((key) => {
              const value = step[key as keyof Step];

              // Handle the "type" field with Select dropdown
              if (key === 'type') {
                return (
                  <div key={key}>
                    <Label className="capitalize">{key}</Label>
                    <Select
                      value={value as string}
                      onValueChange={(val) =>
                        updateStepField(index, key as keyof Step, val)
                      }
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {[
                          'navigation',
                          'click',
                          'select_change',
                          'input',
                          'agent',
                          'key_press',
                        ].map((t) => (
                          <SelectItem key={t} value={t}>
                            {t}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                );
              }

              // Skip these fields for editing
              if (['output', 'timestamp', 'tabId'].includes(key)) return null;
              return (
                <div key={key}>
                  <Label className="capitalize">{key}</Label>
                  <Input
                    value={(value as string) ?? ''}
                    onChange={(e) =>
                      updateStepField(index, key as keyof Step, e.target.value)
                    }
                  />
                </div>
              );
            })}
          </CardContent>
        </Card>
      ))}

      <Button className="w-full bg-purple-600 text-white" onClick={saveChanges}>
        Confirm Changes
      </Button>
    </div>
  );
}
