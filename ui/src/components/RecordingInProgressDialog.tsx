import React from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Loader2 } from 'lucide-react';

interface RecordingInProgressDialogProps {
  onCancel: () => void;
  onContinue: () => void;
  recordingStatus: string;
}

export const RecordingInProgressDialog: React.FC<
  RecordingInProgressDialogProps
> = ({ onCancel, onContinue, recordingStatus }) => {
  const isCancelling = recordingStatus === 'cancelling';

  return (
    <Dialog open={true} onOpenChange={onContinue}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Recording in Progress</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-gray-500">
          {isCancelling
            ? 'Cancelling recording...'
            : 'A workflow recording is currently in progress. Would you like to cancel the recording and continue with your action?'}
        </p>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={onContinue}
            disabled={isCancelling}
          >
            Continue Recording
          </Button>
          <Button
            variant="destructive"
            onClick={onCancel}
            disabled={isCancelling}
          >
            {isCancelling ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Cancelling...
              </>
            ) : (
              'Cancel Recording'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
