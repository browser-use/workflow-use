// --- Workflow Format ---

export interface Workflow {
  workflow_analysis?: string; // Analysis of the workflow for semantic targeting
  steps: Step[];
  name: string; // Consider how to populate these fields
  description: string; // Consider how to populate these fields
  version: string; // Consider how to populate these fields
  input_schema: [];
}

// Radio button specific information
export interface RadioButtonInfo {
  fieldName: string; // The group/field name (e.g., "Marital Status")
  optionValue: string; // The specific option (e.g., "Married")
  allOptions: string[]; // All possible values in the group
}

export type Step =
  | NavigationStep
  | ClickStep
  | InputStep
  | RadioStep
  | SelectStep
  | CheckboxStep
  | KeyPressStep
  | ScrollStep
  | ExtractStep;
// Add other step types here as needed, e.g., TabCreatedStep etc.

export interface BaseStep {
  type: string;
  timestamp: number;
  tabId: number;
  url?: string; // Made optional as not all original events have it directly
}

export interface NavigationStep extends BaseStep {
  type: "navigation";
  url: string; // Navigation implies a URL change
  screenshot?: string; // Optional in source
  frameIdPath?: string; // Optional frame context for iframe navigations
}

export interface ClickStep extends BaseStep {
  type: "click";
  url: string;
  frameUrl: string;
  frameIdPath?: string;
  xpath: string;
  cssSelector?: string; // Optional in source
  elementTag: string;
  elementText: string;
  targetText?: string; // Semantic targeting text (label, placeholder, aria-label, etc.)
  radioButtonInfo?: RadioButtonInfo; // Enhanced radio button information
  screenshot?: string; // Optional in source
}

export interface InputStep extends BaseStep {
  type: "input";
  url: string;
  frameUrl: string;
  frameIdPath?: string;
  xpath: string;
  cssSelector?: string; // Optional in source
  elementTag: string;
  value: string;
  targetText?: string; // Semantic targeting text (label, placeholder, aria-label, etc.)
  screenshot?: string; // Optional in source
}

export interface KeyPressStep extends BaseStep {
  type: "key_press";
  url?: string; // Can be missing if key press happens without element focus? Source is optional.
  frameUrl?: string; // Might be missing
  frameIdPath?: string;
  key: string;
  xpath?: string; // Optional in source
  cssSelector?: string; // Optional in source
  elementTag?: string; // Optional in source
  screenshot?: string; // Optional in source
}

export interface ScrollStep extends BaseStep {
  type: "scroll"; // Changed from scroll_update for simplicity
  targetId: number; // The rrweb ID of the element being scrolled
  scrollX: number;
  scrollY: number;
  frameIdPath?: string;
  // Note: url might be missing if scroll happens on initial load before meta event?
}

export interface RadioStep extends BaseStep {
  type: "radio";
  url: string;
  frameUrl: string;
  frameIdPath?: string;
  xpath: string;
  cssSelector?: string;
  fieldName: string; // The group name (e.g., "Gender")
  selectedOption: string; // The selected value (e.g., "Male")
  options: string[]; // All available options in the group
  targetText?: string;
  screenshot?: string;
}

export interface SelectStep extends BaseStep {
  type: "select";
  url: string;
  frameUrl: string;
  frameIdPath?: string;
  xpath: string;
  cssSelector?: string;
  fieldName: string; // The select field name/label
  selectedOption: string; // The selected text
  selectedValue: string; // The selected value
  options: Array<{ text: string; value: string }>; // All options
  targetText?: string;
  screenshot?: string;
}

export interface CheckboxStep extends BaseStep {
  type: "checkbox";
  url: string;
  frameUrl: string;
  frameIdPath?: string;
  xpath: string;
  cssSelector?: string;
  fieldName: string;
  checked: boolean;
  targetText?: string;
  screenshot?: string;
}

export interface ExtractStep extends BaseStep {
  type: "extract";
  url: string;
  extractionGoal: string; // What information to extract from the page
  output?: string; // Context key to store the extracted data
  screenshot?: string; // Optional in source
}

// Potential future step types based on StoredEvent
// export interface TabCreatedStep extends BaseStep { ... }
// export interface TabActivatedStep extends BaseStep { ... }
// export interface TabRemovedStep extends BaseStep { ... }
