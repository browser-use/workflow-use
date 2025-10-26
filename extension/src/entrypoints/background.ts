// import { eventWithTime } from 'rrweb'; // Type not directly available
import { EventType, IncrementalSource } from "@rrweb/types";
import {
  StoredCustomClickEvent,
  StoredCustomInputEvent,
  StoredCustomKeyEvent,
  StoredEvent,
  StoredRrwebEvent,
  StoredExtractionEvent,
} from "../lib/types";
import {
  ClickStep,
  InputStep,
  KeyPressStep,
  NavigationStep,
  ScrollStep,
  Step,
  Workflow,
  ExtractStep,
} from "../lib/workflow-types";
import {
  HttpEvent,
  HttpRecordingStartedEvent,
  HttpRecordingStoppedEvent,
  HttpWorkflowUpdateEvent,
} from "../lib/message-bus-types";

export default defineBackground(() => {
  // In-memory store for rrweb events, keyed by tabId
  const sessionLogs: { [tabId: number]: StoredEvent[] } = {}; // Use StoredEvent type

  // Store tab information (URL, potentially title)
  const tabInfo: { [tabId: number]: { url?: string; title?: string } } = {};

  // Track recent user interactions to distinguish intentional vs side-effect navigation
  const recentUserInteractions: { [tabId: number]: number } = {}; // timestamp of last user interaction

  let isRecordingEnabled = true; // Default to disabled (OFF)
  let lastWorkflowHash: string | null = null; // Cache for the last logged workflow hash

  const PYTHON_SERVER_ENDPOINT = "http://127.0.0.1:7331/event";

  // Hashing function using SubtleCrypto (SHA-256)
  async function calculateSHA256(str: string): Promise<string> {
    const encoder = new TextEncoder();
    const data = encoder.encode(str);
    const hashBuffer = await crypto.subtle.digest("SHA-256", data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    const hashHex = hashArray
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
    return hashHex;
  }

  // Helper function to send data to the Python server
  async function sendEventToServer(eventData: HttpEvent) {
    try {
      await fetch(PYTHON_SERVER_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(eventData),
      });
    } catch (error) {
      console.warn(
        `Failed to send event to Python server at ${PYTHON_SERVER_ENDPOINT}:`,
        error
      );
    }
  }

  // Function to generate step descriptions for semantic workflows
  function generateStepDescription(step: Step): string | null {
    switch (step.type) {
      case "click":
        return "Click element";
      case "input":
        return "Input element";
      case "navigation":
        return `Navigate to ${step.url}`;
      case "scroll":
        return null; // Scroll steps will have null description like in the example
      case "key_press":
        return "Key press element";
      case "extract":
        return "Extract information with AI";
      default:
        return "Unknown action";
    }
  }

  // Function to broadcast workflow data updates to the console bus
  async function broadcastWorkflowDataUpdate(): Promise<Workflow> {
    // console.log("[DEBUG] broadcastWorkflowDataUpdate: Entered function"); // Optional: Keep for debugging
    const allSteps: Step[] = Object.keys(sessionLogs)
      .flatMap((tabIdStr) => {
        const tabId = parseInt(tabIdStr, 10);
        return convertStoredEventsToSteps(sessionLogs[tabId] || []);
      })
      .sort((a, b) => a.timestamp - b.timestamp); // Sort chronologically

    console.log(`🔄 Processing ${allSteps.length} steps for workflow update`);
    const extractionSteps = allSteps.filter(s => s.type === 'extract');
    console.log(`🤖 Found ${extractionSteps.length} extraction steps:`, extractionSteps);

    // Convert steps to semantic format with proper descriptions
    const semanticSteps = allSteps.map((step) => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const semanticStep: Record<string, any> = {
        ...step,
        description: generateStepDescription(step),
      };

      // Remove internal fields that shouldn't be in the final workflow
      delete semanticStep.timestamp;
      delete semanticStep.tabId;
      delete semanticStep.frameUrl;
      delete semanticStep.xpath;
      delete semanticStep.elementTag;
      delete semanticStep.elementText;
      delete semanticStep.screenshot;

      // Handle different step types specifically
      if (step.type === "scroll") {
        delete semanticStep.targetId;
        // Keep scrollX and scrollY for scroll steps
      } else if (step.type === "extract") {
        // For extraction steps, preserve extractionGoal and url
        // Keep: extractionGoal, url, type, description
        // Already removed: timestamp, tabId, screenshot (these are correct to remove)
        console.log(`🤖 Processing extraction step:`, semanticStep);
      }

      // Convert targetText to target_text for semantic workflow compatibility
      if (semanticStep.targetText) {
        semanticStep.target_text = semanticStep.targetText;
        delete semanticStep.targetText;
      } else {
        // Ensure target_text field exists (set to null if no semantic text available)
        semanticStep.target_text = null;
      }

      return semanticStep as Step;
    });

    const semanticExtractionSteps = semanticSteps.filter(s => s.type === 'extract');
    console.log(`✅ Final semantic steps include ${semanticExtractionSteps.length} extraction steps:`, semanticExtractionSteps);

    // Create the workflowData object for the Python server (semantic format)
    const semanticWorkflowData: Workflow = {
      workflow_analysis: "Semantic version of recorded workflow. Uses visible text to identify elements instead of CSS selectors for improved reliability.",
      name: "Recorded Workflow (Semantic)",
      description: `Recorded on ${new Date().toLocaleString()}`,
      version: "1.0",
      input_schema: [],
      steps: semanticSteps, // Use processed semantic steps
    };

    // Create the workflowData object for the UI (with original targetText)
    const uiWorkflowData: Workflow = {
      workflow_analysis: "Semantic version of recorded workflow. Uses visible text to identify elements instead of CSS selectors for improved reliability.",
      name: "Recorded Workflow (Semantic)",
      description: `Recorded on ${new Date().toLocaleString()}`,
      version: "1.0",
      input_schema: [],
      steps: allSteps, // Use original steps with targetText for UI
    };

    const allStepsString = JSON.stringify(allSteps); // Hash based on allSteps
    const currentWorkflowHash = await calculateSHA256(allStepsString);

    // console.log("[DEBUG] broadcastWorkflowDataUpdate: Current steps hash:", currentWorkflowHash, "Last steps hash:", lastWorkflowHash); // Optional

    // Condition to skip logging if the hash of steps is the same
    if (lastWorkflowHash !== null && currentWorkflowHash === lastWorkflowHash) {
      // console.log("[DEBUG] broadcastWorkflowDataUpdate: Steps unchanged, skipping log."); // Optional
      return uiWorkflowData;
    }

    lastWorkflowHash = currentWorkflowHash;
    // console.log("[DEBUG] broadcastWorkflowDataUpdate: Steps changed, workflowData object:", JSON.parse(JSON.stringify(uiWorkflowData))); // Optional

    // Send semantic workflow update to Python server
    const eventToSend: HttpWorkflowUpdateEvent = {
      type: "WORKFLOW_UPDATE",
      timestamp: Date.now(),
      payload: semanticWorkflowData, // Send semantic format to server
    };
    sendEventToServer(eventToSend);
    return uiWorkflowData; // Return UI format to extension
  }

  // Function to broadcast the recording status to all content scripts and sidepanel
  function broadcastRecordingStatus() {
    const statusString = isRecordingEnabled ? "recording" : "stopped"; // Map boolean to string status
    // Broadcast to Tabs
    chrome.tabs.query({}, (tabs) => {
      tabs.forEach((tab) => {
        if (tab.id) {
          chrome.tabs
            .sendMessage(tab.id, {
              type: "SET_RECORDING_STATUS",
              payload: isRecordingEnabled,
            })
            .catch((_err: Error) => {
              // Optional: Log if sending to a specific tab failed (e.g., script not injected)
              // console.debug(`Could not send status to tab ${tab.id}: ${_err.message}`);
            });
        }
      });
    });
    // Broadcast to Sidepanel (using runtime message)
    chrome.runtime
      .sendMessage({
        type: "recording_status_updated",
        payload: { status: statusString }, // Send string status
      })
      .catch((_err) => {
        // console.debug("Could not send status update to sidepanel (might be closed)", _err.message);
      });
  }

  // --- Tab Event Listeners ---

  // Function to send tab events (only if recording is enabled)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  function sendTabEvent(type: string, payload: Record<string, any>) {
    if (!isRecordingEnabled) return;
    console.log(`Sending ${type}:`, payload);
    const tabId = payload.tabId;
    if (tabId) {
      if (!sessionLogs[tabId]) {
        sessionLogs[tabId] = [];
      }
      sessionLogs[tabId].push({
        messageType: type as StoredEvent["messageType"],
        timestamp: Date.now(),
        tabId: tabId,
        ...payload,
      } as StoredEvent);
      broadcastWorkflowDataUpdate(); // Call is async, will not block
    } else {
      console.warn(
        "Tab event received without tabId in payload:",
        type,
        payload
      );
      // Optionally store in a global log?
    }
  }

  chrome.tabs.onCreated.addListener((tab) => {
    sendTabEvent("CUSTOM_TAB_CREATED", {
      tabId: tab.id,
      openerTabId: tab.openerTabId,
      url: tab.pendingUrl || tab.url,
      windowId: tab.windowId,
      index: tab.index,
    });
  });

  chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    // Filter for relevant changes (e.g., url or status complete)
    if (changeInfo.url || changeInfo.status === "complete") {
      sendTabEvent("CUSTOM_TAB_UPDATED", {
        tabId: tabId,
        changeInfo: changeInfo, // includes URL, status, title etc.
        windowId: tab.windowId,
        url: tab.url,
        title: tab.title,
      });
    }
  });

  chrome.tabs.onActivated.addListener((activeInfo) => {
    sendTabEvent("CUSTOM_TAB_ACTIVATED", {
      tabId: activeInfo.tabId,
      windowId: activeInfo.windowId,
    });
  });

  chrome.tabs.onRemoved.addListener((tabId, removeInfo) => {
    sendTabEvent("CUSTOM_TAB_REMOVED", {
      tabId: tabId,
      windowId: removeInfo.windowId,
      isWindowClosing: removeInfo.isWindowClosing,
    });
    // Optional: Clean up logs for the closed tab if desired (we keep them by default)
    // if (sessionLogs[tabId]) {
    //   console.log(`Tab ${tabId} closed, removing logs.`);
    //   delete sessionLogs[tabId];
    //   delete tabInfo[tabId];
    // }
  });

  // --- End Tab Event Listeners ---

  // --- Conversion Function ---

  function convertStoredEventsToSteps(events: StoredEvent[]): Step[] {
    const steps: Step[] = [];

    for (const event of events) {
      switch (event.messageType) {
        case "CUSTOM_CLICK_EVENT": {
          const clickEvent = event as StoredCustomClickEvent;
          // Ensure required fields are present, even if optional in source type for some reason
          if (
            clickEvent.url &&
            clickEvent.frameUrl &&
            clickEvent.xpath &&
            clickEvent.elementTag
          ) {
            const step: ClickStep = {
              type: "click",
              timestamp: clickEvent.timestamp,
              tabId: clickEvent.tabId,
              url: clickEvent.url,
              frameUrl: clickEvent.frameUrl,
              xpath: clickEvent.xpath,
              elementTag: clickEvent.elementTag,
              elementText: clickEvent.elementText,
              screenshot: clickEvent.screenshot,
            };
            
            // Prioritize target_text for semantic workflows, but include cssSelector for complex elements
            if (clickEvent.targetText && clickEvent.targetText.trim()) {
              step.targetText = clickEvent.targetText;
              
              // For radio buttons, checkboxes, and complex interactive elements, also include cssSelector
              if (clickEvent.cssSelector && 
                  (clickEvent.cssSelector.includes('radio') || 
                   clickEvent.cssSelector.includes('checkbox') ||
                   clickEvent.cssSelector.includes('role="radio"') ||
                   clickEvent.cssSelector.includes('role="checkbox"') ||
                   clickEvent.elementTag.toLowerCase() === 'button')) {
                step.cssSelector = clickEvent.cssSelector;
              }
            } else if (clickEvent.cssSelector) {
              step.cssSelector = clickEvent.cssSelector;
            }
            
            steps.push(step);
          } else {
            console.warn("Skipping incomplete CUSTOM_CLICK_EVENT:", clickEvent);
          }
          break;
        }

        case "CUSTOM_INPUT_EVENT": {
          const inputEvent = event as StoredCustomInputEvent;
          if (
            inputEvent.url &&
            // inputEvent.frameUrl && // frameUrl might be null/undefined in some cases, let's allow merging if only one is present or both match
            inputEvent.xpath &&
            inputEvent.elementTag
          ) {
            const lastStep = steps.length > 0 ? steps[steps.length - 1] : null;

            // Check if the last step was a mergeable input event
            if (
              lastStep &&
              lastStep.type === "input" &&
              lastStep.tabId === inputEvent.tabId &&
              lastStep.url === inputEvent.url &&
              lastStep.frameUrl === inputEvent.frameUrl && // Ensure frameUrls match if both exist
              lastStep.xpath === inputEvent.xpath &&
              ((lastStep as InputStep).targetText === inputEvent.targetText || 
               (lastStep as InputStep).cssSelector === inputEvent.cssSelector) &&
              lastStep.elementTag === inputEvent.elementTag
            ) {
              // Update the last input step
              (lastStep as InputStep).value = inputEvent.value;
              lastStep.timestamp = inputEvent.timestamp; // Update to latest timestamp
              (lastStep as InputStep).screenshot = inputEvent.screenshot; // Update to latest screenshot
              
              // Update semantic targeting if available
              if (inputEvent.targetText && inputEvent.targetText.trim()) {
                (lastStep as InputStep).targetText = inputEvent.targetText;
                delete (lastStep as InputStep).cssSelector; // Remove cssSelector when we have targetText
              }
            } else {
              // Add a new input step
              const newStep: InputStep = {
                type: "input",
                timestamp: inputEvent.timestamp,
                tabId: inputEvent.tabId,
                url: inputEvent.url,
                frameUrl: inputEvent.frameUrl,
                xpath: inputEvent.xpath,
                elementTag: inputEvent.elementTag,
                value: inputEvent.value,
                screenshot: inputEvent.screenshot,
              };
              
              // Prioritize target_text for semantic workflows, but include cssSelector for complex elements
              if (inputEvent.targetText && inputEvent.targetText.trim()) {
                newStep.targetText = inputEvent.targetText;
                
                // For radio buttons, checkboxes, and complex input elements, also include cssSelector
                if (inputEvent.cssSelector && 
                    (inputEvent.cssSelector.includes('radio') || 
                     inputEvent.cssSelector.includes('checkbox') ||
                     inputEvent.cssSelector.includes('role="radio"') ||
                     inputEvent.cssSelector.includes('role="checkbox"'))) {
                  newStep.cssSelector = inputEvent.cssSelector;
                }
              } else if (inputEvent.cssSelector) {
                newStep.cssSelector = inputEvent.cssSelector;
              }
              
              steps.push(newStep);
            }
          } else {
            console.warn("Skipping incomplete CUSTOM_INPUT_EVENT:", inputEvent);
          }
          break;
        }

        case "CUSTOM_KEY_EVENT": {
          const keyEvent = event as StoredCustomKeyEvent;
          // Key press might not always have a target element (xpath, etc.)
          // but needs at least url and key
          if (keyEvent.url && keyEvent.key) {
            const step: KeyPressStep = {
              type: "key_press",
              timestamp: keyEvent.timestamp,
              tabId: keyEvent.tabId,
              url: keyEvent.url,
              frameUrl: keyEvent.frameUrl, // Can be missing
              key: keyEvent.key,
              xpath: keyEvent.xpath,
              cssSelector: keyEvent.cssSelector,
              elementTag: keyEvent.elementTag,
              screenshot: keyEvent.screenshot,
            };
            steps.push(step);
          } else {
            console.warn("Skipping incomplete CUSTOM_KEY_EVENT:", keyEvent);
          }
          break;
        }

        case "RRWEB_EVENT": {
          // We only care about scroll events from rrweb for now
          const rrEvent = event as StoredRrwebEvent;
          if (
            rrEvent.type === EventType.IncrementalSnapshot &&
            rrEvent.data.source === IncrementalSource.Scroll
          ) {
            const scrollData = rrEvent.data as {
              id: number;
              x: number;
              y: number;
            }; // Type assertion for clarity
            const currentTabInfo = tabInfo[rrEvent.tabId]; // Get associated tab info for URL

            // Check if the last step added was a mergeable scroll event
            const lastStep = steps.length > 0 ? steps[steps.length - 1] : null;
            if (
              lastStep &&
              lastStep.type === "scroll" &&
              lastStep.tabId === rrEvent.tabId &&
              (lastStep as ScrollStep).targetId === scrollData.id
            ) {
              // Update the last scroll step
              (lastStep as ScrollStep).scrollX = scrollData.x;
              (lastStep as ScrollStep).scrollY = scrollData.y;
              lastStep.timestamp = rrEvent.timestamp; // Update to latest timestamp
              // URL should already be set from the first event in the sequence
            } else {
              // Add a new scroll step
              const newStep: ScrollStep = {
                type: "scroll",
                timestamp: rrEvent.timestamp,
                tabId: rrEvent.tabId,
                targetId: scrollData.id,
                scrollX: scrollData.x,
                scrollY: scrollData.y,
                url: currentTabInfo?.url, // Add URL if available
              };
              steps.push(newStep);
            }
          } else if ((rrEvent.type === EventType.Meta || rrEvent.type === EventType.FullSnapshot) && rrEvent.data?.href) {
            // Handle rrweb meta and fullsnapshot events as navigation (filtering now happens at storage level)
            const metaData = rrEvent.data as { href: string };
            const step: NavigationStep = {
              type: "navigation",
              timestamp: rrEvent.timestamp,
              tabId: rrEvent.tabId,
              url: metaData.href,
            };
            steps.push(step);
          }
          break;
        }

        case "EXTRACTION_STEP": {
          const extractEvent = event as StoredExtractionEvent;
          if (extractEvent.url && extractEvent.extractionGoal) {
            const step: ExtractStep = {
              type: "extract",
              timestamp: extractEvent.timestamp,
              tabId: extractEvent.tabId,
              url: extractEvent.url,
              extractionGoal: extractEvent.extractionGoal,
              screenshot: extractEvent.screenshot,
            };
            steps.push(step);
          } else {
            console.warn("Skipping incomplete EXTRACTION_STEP:", extractEvent);
          }
          break;
        }

        // Add cases for other StoredEvent types to Step types if needed
        // e.g., CUSTOM_SELECT_EVENT -> SelectStep
        // e.g., CUSTOM_TAB_CREATED -> TabCreatedStep
        // RRWEB_EVENT type 4 (Meta) or 3 (FullSnapshot) could potentially map to NavigationStep if needed.

        default:
          // Ignore other event types for now
          // console.log("Ignoring event type:", event.messageType);
          break;
      }
    }

    return steps;
  }

  // --- Message Listener ---

  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    let isAsync = false; // Flag to indicate if sendResponse will be called asynchronously

    // --- Event Listener from Content Scripts ---
    const customEventTypes = [
      "CUSTOM_CLICK_EVENT",
      "CUSTOM_INPUT_EVENT",
      "CUSTOM_SELECT_EVENT",
      "CUSTOM_KEY_EVENT",
    ];
    if (
      message.type === "RRWEB_EVENT" ||
      customEventTypes.includes(message.type)
    ) {
      if (!isRecordingEnabled) {
        return false; // Don't process if disabled, not async
      }
      if (!sender.tab?.id) {
        console.warn("Received event without tab ID:", message);
        return false; // Ignore events without a tab ID, not async
      }

      const tabId = sender.tab.id;
      const isCustomEvent = customEventTypes.includes(message.type);

      // Function to store the event
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const storeEvent = (eventPayload: Record<string, any>, screenshotDataUrl?: string) => {
        if (!sessionLogs[tabId]) {
          sessionLogs[tabId] = [];
        }
        if (!tabInfo[tabId]) {
          tabInfo[tabId] = {};
        }
        if (sender.tab?.url && !tabInfo[tabId].url) {
          tabInfo[tabId].url = sender.tab.url;
        }
        if (sender.tab?.title && !tabInfo[tabId].title) {
          tabInfo[tabId].title = sender.tab.title;
        }

        // Track user interactions for navigation filtering
        if (customEventTypes.includes(message.type)) {
          recentUserInteractions[tabId] = eventPayload.timestamp || Date.now();
          console.log(`[NAV_FILTER] Tracked ${message.type} on tab ${tabId} at ${recentUserInteractions[tabId]}`);
        }

        // Log all rrweb events for debugging
        if (message.type === "RRWEB_EVENT") {
          console.log(`[NAV_FILTER] RRWEB event type ${eventPayload.type} (Meta=${EventType.Meta})`, eventPayload.data);
        }

        // Filter out side-effect navigation from rrweb meta and fullsnapshot events
        if (message.type === "RRWEB_EVENT" && 
            (eventPayload.type === EventType.Meta || eventPayload.type === EventType.FullSnapshot) && 
            eventPayload.data?.href) {
          const lastUserInteraction = recentUserInteractions[tabId] || 0;
          const currentTime = eventPayload.timestamp || Date.now();
          const timeSinceLastInteraction = currentTime - lastUserInteraction;
          
          // Check if this is the first event in the session (initial page load)
          const isFirstEvent = !sessionLogs[tabId] || sessionLogs[tabId].length === 0;
          
          // Only store navigation if it's the first event (initial page load) or no user interaction has happened
          if (lastUserInteraction === 0 || isFirstEvent) {
            console.log(`[NAV_FILTER] STORING navigation: ${eventPayload.data.href} (lastInteraction: ${lastUserInteraction}, isFirst: ${isFirstEvent})`);
          } else {
            console.log(`[NAV_FILTER] FILTERED navigation: ${eventPayload.data.href} (${timeSinceLastInteraction}ms after interaction - always filter post-interaction navigation)`);
            return; // Don't store this event
          }
        }

        const eventWithMeta: StoredEvent = {
          ...eventPayload,
          tabId: tabId,
          messageType: message.type,
          screenshot: screenshotDataUrl,
        } as StoredEvent;
        sessionLogs[tabId].push(eventWithMeta);
        broadcastWorkflowDataUpdate(); // Call is async, will not block
        // console.log(`Stored ${message.type} from tab ${tabId}`);
      };

      // If it's a custom event from content script, try capture screenshot
      if (isCustomEvent && sender.tab?.windowId) {
        isAsync = true; // Indicate async response for screenshot capture
        chrome.tabs.captureVisibleTab(
          sender.tab.windowId,
          { format: "jpeg", quality: 75 },
          (dataUrl) => {
            if (chrome.runtime.lastError) {
              console.error(
                "Screenshot failed:",
                chrome.runtime.lastError.message
              );
              storeEvent(message.payload); // Store event without screenshot
            } else {
              storeEvent(message.payload, dataUrl); // Store event with screenshot
            }
            // Note: sendResponse is not called here, as the event listener just stores data
          }
        );
      } else if (message.type === "RRWEB_EVENT") {
        // For RRWEB_EVENT, store immediately (synchronous)
        storeEvent(message.payload);
      } else if (isCustomEvent) {
        // Custom event but couldn't get screenshot (e.g., missing windowId)
        console.warn(
          "Storing custom event without screenshot due to missing windowId or other issue."
        );
        storeEvent(message.payload);
      }
    }

    // --- Control Messages from Sidepanel ---
    else if (message.type === "GET_RECORDING_DATA") {
      isAsync = true; // Indicate async response for sendResponse
      (async () => {
        const workflowData = await broadcastWorkflowDataUpdate();

        const statusString = isRecordingEnabled
          ? "recording"
          : workflowData.steps.length > 0
          ? "stopped"
          : "idle";

        sendResponse({ workflow: workflowData, recordingStatus: statusString });
      })();
      return isAsync; // Crucial: return true to keep message channel open for async sendResponse
    } else if (message.type === "START_RECORDING") {
      console.log("Received START_RECORDING request.");
      // Clear previous data
      Object.keys(sessionLogs).forEach(
        (key) => delete sessionLogs[parseInt(key)]
      );
      Object.keys(tabInfo).forEach((key) => delete tabInfo[parseInt(key)]);
      Object.keys(recentUserInteractions).forEach(
        (key) => delete recentUserInteractions[parseInt(key)]
      );
      console.log("Cleared previous recording data.");

      // Start recording
      if (!isRecordingEnabled) {
        isRecordingEnabled = true;
        console.log("Recording status set to: true");
        broadcastRecordingStatus(); // Inform content scripts and sidepanel

        // Send recording started event to Python server
        const eventToSend: HttpRecordingStartedEvent = {
          type: "RECORDING_STARTED",
          timestamp: Date.now(),
          payload: { message: "Recording has started" },
        };
        sendEventToServer(eventToSend);
      }
      sendResponse({ status: "started" }); // Send simple confirmation
    } else if (message.type === "STOP_RECORDING") {
      console.log("Received STOP_RECORDING request.");
      if (isRecordingEnabled) {
        isRecordingEnabled = false;
        console.log("Recording status set to: false");
        broadcastRecordingStatus(); // Inform content scripts and sidepanel

        // Send recording stopped event to Python server
        const eventToSend: HttpRecordingStoppedEvent = {
          type: "RECORDING_STOPPED",
          timestamp: Date.now(),
          payload: { message: "Recording has stopped" },
        };
        sendEventToServer(eventToSend);
      }
      sendResponse({ status: "stopped" }); // Send simple confirmation
    }
    // --- Add Extraction Step from Sidepanel ---
    else if (message.type === "ADD_EXTRACTION_STEP") {
      console.log("🤖 Received ADD_EXTRACTION_STEP request:", message.payload);
      
      if (!isRecordingEnabled) {
        console.error("❌ Recording is not enabled");
        sendResponse({ status: "error", message: "Recording is not active" });
        return false;
      }

      try {
        // For sidepanel messages, we need to get the active tab
        // Since this is from sidepanel, sender.tab will be undefined
        // Let's use a direct approach with chrome.tabs.query but handle it synchronously
        
        isAsync = true;
        
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
          try {
            console.log("📋 Active tabs found:", tabs?.length || 0);
            
            if (chrome.runtime.lastError) {
              console.error("❌ Chrome tabs query error:", chrome.runtime.lastError);
              sendResponse({ status: "error", message: "Chrome tabs query failed" });
              return;
            }
            
            if (!tabs || tabs.length === 0 || !tabs[0]?.id) {
              console.error("❌ No active tab found");
              sendResponse({ status: "error", message: "No active tab found" });
              return;
            }

            const tabId = tabs[0].id;
            const tabUrl = tabs[0].url || "";
            
            console.log("✅ Using tab ID:", tabId, "URL:", tabUrl);
            
            const extractionStep: StoredExtractionEvent = {
              timestamp: message.payload.timestamp,
              tabId: tabId,
              url: tabUrl,
              extractionGoal: message.payload.extractionGoal,
              messageType: "EXTRACTION_STEP",
            };

            console.log("📝 Creating extraction step:", extractionStep);

            if (!sessionLogs[tabId]) {
              console.log("🆕 Initializing sessionLogs for tab:", tabId);
              sessionLogs[tabId] = [];
            }
            
            sessionLogs[tabId].push(extractionStep);
            console.log("✅ Added extraction step to sessionLogs. Total events for tab:", sessionLogs[tabId].length);
            
            // Broadcast update (don't await to avoid blocking)
            broadcastWorkflowDataUpdate();
            console.log("✅ Broadcasted workflow update");
            
            // Send success response
            sendResponse({ status: "added" });
            
          } catch (error) {
            console.error("❌ Error in tabs.query callback:", error);
            sendResponse({ status: "error", message: `Callback error: ${error}` });
          }
        });
        
        return true; // Keep message channel open
        
      } catch (error) {
        console.error("❌ Error setting up extraction step:", error);
        sendResponse({ status: "error", message: `Setup error: ${error}` });
        return false;
      }
    }
    // --- Status Request from Content Script ---
    else if (message.type === "REQUEST_RECORDING_STATUS" && sender.tab?.id) {
      console.log(
        `Sending initial status (${isRecordingEnabled}) to tab ${sender.tab.id}`
      );
      sendResponse({ isRecordingEnabled });
    }

    // --- Removed Handlers ---
    // else if (message.type === "CLEAR_RECORDING_DATA") { ... } // Now handled by START_RECORDING
    // else if (message.type === "GET_RECORDING_STATUS") { ... } // Sidepanel uses GET_RECORDING_DATA
    // else if (message.type === "TOGGLE_RECORDING") { ... } // Replaced by START/STOP

    // Return true if sendResponse will be called asynchronously (screenshotting, GET_RECORDING_DATA)
    // Otherwise, return false or undefined (implicitly false).
    return isAsync;
  });

  // Optional: Save data periodically or on browser close (less reliable)
  // chrome.storage.local.set({ sessionLogs, tabInfo });

  console.log(
    "Background script loaded. Initial recording status:",
    isRecordingEnabled,
    "(EventType:",
    EventType,
    ", IncrementalSource:",
    IncrementalSource,
    ")" // Log imported constants
  );

  // Automatically open the side panel on install/update during development
  // Note: chrome.sidePanel.open() typically requires a user gesture,
  // but onInstalled sometimes works for development reloads.
  if (import.meta.env.DEV) {
    chrome.runtime.onInstalled.addListener(async (details) => {
      // Only run on development install/update
      if (details.reason === "install" || details.reason === "update") {
        console.log(
          `[DEV] Extension ${details.reason}ed. Attempting to open side panel...`
        );
        try {
          // We need to specify the window ID to open the global side panel.
          // Using getLastFocused is generally safer than getCurrent() here.
          const window = await chrome.windows.getLastFocused();
          if (window?.id) {
            await chrome.sidePanel.open({ windowId: window.id });
            console.log(
              `[DEV] Side panel open call successful for window ${window.id}.`
            );
          } else {
            console.warn(
              "[DEV] Could not get window ID to open side panel (no focused window?)."
            );
          }
        } catch (error) {
          console.error("[DEV] Error opening side panel:", error);
          console.warn(
            "[DEV] Note: Automatic side panel opening might fail without a direct user gesture or if no window is focused."
          );
        }
      }
    });
  }

  // Also allow opening via the action icon click (works in dev and prod)
  chrome.sidePanel
    .setPanelBehavior({ openPanelOnActionClick: true })
    .catch((error) => console.error("Failed to set panel behavior:", error));
});
