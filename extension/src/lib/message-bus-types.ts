import type { Workflow } from "./workflow-types";

// Types for events sent via HTTP to the Python server

export interface HttpWorkflowUpdateEvent {
  type: "WORKFLOW_UPDATE";
  timestamp: number;
  payload: Workflow;
}

export interface HttpRecordingStartedEvent {
  type: "RECORDING_STARTED";
  timestamp: number;
  payload: {
    message: string;
  };
}

export interface HttpRecordingStoppedEvent {
  type: "RECORDING_STOPPED";
  timestamp: number;
  payload: {
    message: string;
  };
}

// If you plan to send other types of events, like TERMINATE_COMMAND, define them here too
// export interface HttpTerminateCommandEvent {
//   type: "TERMINATE_COMMAND";
//   timestamp: number;
//   payload: {
//     reason?: string; // Optional reason for termination
//   };
// }

export type HttpEvent =
  | HttpWorkflowUpdateEvent
  | HttpRecordingStartedEvent
  | HttpRecordingStoppedEvent;
// | HttpTerminateCommandEvent; // Add other event types to the union if defined
