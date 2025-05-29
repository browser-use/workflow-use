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
  const { activeDialog, setActiveDialog, currentWorkflowData } =
    useAppContext();
  const [prompt, setPrompt] = useState('');
  const [isExecuting, setIsExecuting] = useState(false);

  const executeWorkflowAsTool = async () => {
    setIsExecuting(true);
    console.log('Executing workflow as tool with prompt:', prompt);

    // Simulate LLM processing and workflow execution
    await new Promise((resolve) => setTimeout(resolve, 5000));

    setIsExecuting(false);
    setActiveDialog(null);
    setPrompt(''); // Reset prompt
  };

  if (!currentWorkflowData) return null;

  return (
    <Dialog
      open={activeDialog === 'runAsTool'}
      onOpenChange={(open) => setActiveDialog(open ? 'runAsTool' : null)}
    >
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <div className="text-center p-6 bg-gradient-to-r from-purple-500 to-indigo-500 rounded-lg shadow-lg">
          <p className="text-2xl font-bold text-white">🚀 Coming Soon!</p>
          <p className="text-md text-white mt-2">
            This feature is currently under development. Stay tuned for updates!
          </p>
        </div>
        <br />
        <DialogHeader>
          <DialogTitle className="text-xl font-semibold">
            Run as Tool: {currentWorkflowData.name}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-6 py-4">
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
              setActiveDialog(null);
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
