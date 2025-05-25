import React, { useState } from 'react';
import { z } from 'zod';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '@/components/ui/select';
import { GripVertical, Trash2 } from 'lucide-react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { stepSchema } from '@/types/workflow-layout.types';

type Step = z.infer<typeof stepSchema>;

interface SortableStepProps {
  step: Step;
  index: number;
  onDelete: (index: number) => void;
  onUpdate: (index: number, key: keyof Step, value: any) => void;
}

export function SortableStep({
  step,
  index,
  onDelete,
  onUpdate,
}: SortableStepProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: index });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    position: 'relative' as const,
    zIndex: isDragging ? 1 : 0,
    touchAction: 'none',
  };

  return (
    <Card
      ref={setNodeRef}
      style={style}
      className={`bg-white ${isDragging ? 'shadow-lg' : ''}`}
    >
      <CardHeader className="pb-2">
        <CardTitle className="flex justify-between items-center">
          <span className="flex gap-2 items-center">
            <GripVertical
              className="w-4 h-4 text-gray-400 cursor-grab"
              {...attributes}
              {...listeners}
            />
            Step {index + 1}
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onDelete(index)}
            className="text-red-600 hover:text-red-700"
          >
            <Trash2 className="w-4 h-4" />
          </Button>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="space-y-2">
          <div>
            <Label className="capitalize">type</Label>
            <Select
              value={step.type}
              onValueChange={(val) => onUpdate(index, 'type', val)}
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

          <div>
            <Label className="capitalize">description</Label>
            <Input
              value={step.description}
              onChange={(e) => onUpdate(index, 'description', e.target.value)}
            />
          </div>
        </div>

        <div
          className={`overflow-hidden transition-all duration-200 ${
            isExpanded ? 'max-h-[500px] opacity-100' : 'max-h-0 opacity-0'
          }`}
        >
          <div className="space-y-2">
            {Object.keys(step).map((key) => {
              const value = step[key as keyof Step];
              if (
                [
                  'type',
                  'description',
                  'output',
                  'timestamp',
                  'tabId',
                ].includes(key)
              )
                return null;

              return (
                <div key={key}>
                  <Label className="capitalize">{key}</Label>
                  <Input
                    value={(value as string) ?? ''}
                    onChange={(e) =>
                      onUpdate(index, key as keyof Step, e.target.value)
                    }
                  />
                </div>
              );
            })}
          </div>
        </div>

        <div className="pt-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsExpanded(!isExpanded)}
            className="w-full hover:bg-gray-100"
          >
            {isExpanded ? 'Show Less' : 'Show More'}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
