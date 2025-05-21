export interface LogViewerProps {
  taskId: string | null;
  initialPosition: number;
  onStatusChange?: (status: string) => void;
  onError?: (error: string) => void;
  onCancel?: () => void;
  onClose?: () => void;
}