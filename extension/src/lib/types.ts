export interface StoredCustomClickEvent {
  timestamp: number;
  url: string;
  frameUrl: string;
  xpath: string;
  cssSelector?: string;
  elementTag: string;
  elementText: string;
  targetText?: string; // Semantic targeting text
  tabId: number;
  messageType: "CUSTOM_CLICK_EVENT";
  screenshot?: string;
}

export interface StoredCustomInputEvent {
  timestamp: number;
  url: string;
  frameUrl: string;
  xpath: string;
  cssSelector?: string;
  elementTag: string;
  value: string;
  targetText?: string; // Semantic targeting text
  tabId: number;
  messageType: "CUSTOM_INPUT_EVENT";
  screenshot?: string;
}

export interface StoredCustomSelectEvent {
  timestamp: number;
  url: string;
  frameUrl: string;
  xpath: string;
  cssSelector?: string;
  elementTag: string;
  selectedValue: string;
  selectedText: string;
  tabId: number;
  messageType: "CUSTOM_SELECT_EVENT";
  screenshot?: string;
}

export interface StoredCustomKeyEvent {
  timestamp: number;
  url: string;
  frameUrl: string;
  key: string;
  xpath?: string; // XPath of focused element
  cssSelector?: string;
  elementTag?: string;
  tabId: number;
  messageType: "CUSTOM_KEY_EVENT";
  screenshot?: string;
}

export interface StoredExtractionEvent {
  timestamp: number;
  url: string;
  tabId: number;
  extractionGoal: string;
  messageType: "EXTRACTION_STEP";
  screenshot?: string;
}

export interface StoredTabEvent {
  timestamp: number;
  tabId: number;
  messageType:
    | "CUSTOM_TAB_CREATED"
    | "CUSTOM_TAB_UPDATED"
    | "CUSTOM_TAB_ACTIVATED"
    | "CUSTOM_TAB_REMOVED";
  url?: string;
  openerTabId?: number;
  windowId?: number;
  changeInfo?: chrome.tabs.TabChangeInfo; // Relies on chrome types
  isWindowClosing?: boolean;
  index?: number;
  title?: string;
}

export interface StoredRrwebEvent {
  type: number; // rrweb EventType (consider importing if needed)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: any;
  timestamp: number;
  tabId: number;
  messageType: "RRWEB_EVENT";
}

export type StoredEvent =
  | StoredCustomClickEvent
  | StoredCustomInputEvent
  | StoredCustomSelectEvent
  | StoredCustomKeyEvent
  | StoredTabEvent
  | StoredRrwebEvent
  | StoredExtractionEvent;

// --- Data Structures ---

export interface TabData {
  info: { url?: string; title?: string };
  events: StoredEvent[];
}

export interface RecordingData {
  [tabId: number]: TabData;
}
