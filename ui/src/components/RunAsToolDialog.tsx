import React, { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { useAppContext } from '@/contexts/AppContext';
import { Settings, Loader2 } from 'lucide-react';

export function RunAsToolDialog() {
  const { showRunAsToolDialog, setShowRunAsToolDialog, currentWorkflowData } =
    useAppContext();
  const [prompt, setPrompt] = useState('');
  const [isExecuting, setIsExecuting] = useState(false);

  const executeWorkflowAsTool = async () => {
    setIsExecuting(true);
    console.log('Executing workflow as tool with prompt:', prompt);

    // Simulate LLM processing and workflow execution
    await new Promise((resolve) => setTimeout(resolve, 5000));

    setIsExecuting(false);
    setShowRunAsToolDialog(false);
    setPrompt(''); // Reset prompt
  };

  if (!currentWorkflowData) return null;

  return (
    <Dialog open={showRunAsToolDialog} onOpenChange={setShowRunAsToolDialog}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-xl font-semibold">
            Run as Tool: {currentWorkflowData.name}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-6 py-4">
          <div className="text-center p-4 bg-gray-100 rounded-lg">
            <p className="text-lg font-semibold text-gray-700">Coming Soon</p>
            <p className="text-sm text-gray-600 mt-1">
              This feature is currently under development
            </p>
          </div>
          <p className="text-gray-600">
            Provide a prompt for the LLM to generate the inputs for this
            workflow:
          </p>

          <div className="space-y-2">
            <Label htmlFor="llm-prompt" className="text-sm font-medium">
              LLM Prompt
            </Label>
            <textarea
              id="llm-prompt"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Describe how you want the workflow to be executed..."
              className="flex min-h-[120px] w-full rounded-md border border-input bg-background px-3 py-2 text-base ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 md:text-sm resize-none"
              rows={6}
            />
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => {
              setShowRunAsToolDialog(false);
              setPrompt('');
            }}
            disabled={isExecuting}
          >
            Cancel
          </Button>
          <Button
            onClick={executeWorkflowAsTool}
            disabled={isExecuting || !prompt.trim()}
            className="bg-purple-600 hover:bg-purple-700 text-white flex items-center gap-2"
          >
            {isExecuting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Processing...
              </>
            ) : (
              <>
                <Settings className="w-4 h-4" />
                Run as Tool
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
