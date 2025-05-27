import React from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';

interface RecordingInProgressDialogProps {
  onCancel: () => void;
  onContinue: () => void;
}

export const RecordingInProgressDialog: React.FC<
  RecordingInProgressDialogProps
> = ({ onCancel, onContinue }) => {
  return (
    <Dialog open={true} onOpenChange={onContinue}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Recording in Progress</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-gray-500">
          A workflow recording is currently in progress. Would you like to
          cancel the recording and continue with your action?
        </p>
        <DialogFooter>
          <Button variant="outline" onClick={onContinue}>
            Continue Recording
          </Button>
          <Button variant="destructive" onClick={onCancel}>
            Cancel Recording
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
