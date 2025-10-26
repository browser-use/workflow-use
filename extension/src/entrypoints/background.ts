// import { eventWithTime } from 'rrweb'; // Type not directly available
import { EventType, IncrementalSource } from "@rrweb/types";
import {
  StoredCustomClickEvent,
  StoredCustomInputEvent,
  StoredCustomKeyEvent,
  StoredEvent,
  StoredRrwebEvent,
} from "../lib/types";
import {
  ClickStep,
  InputStep,
  KeyPressStep,
  NavigationStep,
  ScrollStep,
  Step,
  Workflow,
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

  // Track which tabs have been explicitly activated (brought to foreground) by the user.
  // We will ignore events originating from tabs that were never activated to reduce noise
  // (for example: ad / tracker tabs that load in the background).
  const activatedTabs = new Set<number>();

  // Track user clicks that are likely to open a new tab (Ctrl/Cmd + click, target=_blank etc.).
  // Content scripts will send a PREPARE_NEW_TAB signal; we keep timestamp to correlate
  // shortly following chrome.tabs.onCreated events so we can mark those tabs as user initiated.
  const recentNewTabIntents: { [openerTabId: number]: number } = {};
  // Record iframe URLs that the user actually interacted with (via custom events) per tab
  const interactedFrameUrls: Record<number, Set<string>> = {};
  // Additionally track last interaction time per frame for time-window gating
  const interactedFrameTimes: Record<number, Record<string, number>> = {};
  // Heuristic window (ms) within which a created tab following a user intent is considered relevant.
  const NEW_TAB_INTENT_WINDOW_MS = 4000;

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

  // Function to broadcast workflow data updates to the console bus
  async function broadcastWorkflowDataUpdate(): Promise<Workflow> {
    await settingsReady;
    // console.log("[DEBUG] broadcastWorkflowDataUpdate: Entered function"); // Optional: Keep for debugging
    const rawSteps: Step[] = Object.keys(sessionLogs)
      .flatMap((tabIdStr) => {
        const tabId = parseInt(tabIdStr, 10);
        return convertStoredEventsToSteps(sessionLogs[tabId] || []);
      })
      .sort((a, b) => a.timestamp - b.timestamp); // Sort chronologically

    // Post-process to collapse consecutive duplicates that only differ by timestamp (e.g. repeated identical navigations)
    const allSteps: Step[] = [];
    for (const step of rawSteps) {
      const last = allSteps.length ? allSteps[allSteps.length - 1] : null;
      if (!last) {
        allSteps.push(step);
        continue;
      }
      let isDuplicate = false;
      if (last.type === step.type) {
        switch (step.type) {
          case 'navigation':
            isDuplicate = (last as NavigationStep).url === (step as NavigationStep).url && last.tabId === step.tabId;
            break;
          case 'input':
            isDuplicate =
              last.tabId === step.tabId &&
              (last as any).url === (step as any).url &&
              (last as any).frameUrl === (step as any).frameUrl &&
              (last as any).xpath === (step as any).xpath &&
              (last as any).elementTag === (step as any).elementTag &&
              (last as any).value === (step as any).value;
            break;
          case 'click':
            isDuplicate =
              last.tabId === step.tabId &&
              (last as any).url === (step as any).url &&
              (last as any).frameUrl === (step as any).frameUrl &&
              (last as any).xpath === (step as any).xpath &&
              (last as any).elementTag === (step as any).elementTag &&
              (last as any).elementText === (step as any).elementText;
            break;
          case 'scroll': {
            const sameXY = (last as any).scrollX === (step as any).scrollX && (last as any).scrollY === (step as any).scrollY;
            const sameUrl = (last as any).url === (step as any).url;
            const nearTime = Math.abs(step.timestamp - last.timestamp) < 200;
            isDuplicate = last.tabId === step.tabId && sameXY && sameUrl && nearTime;
            break;
          }
          case 'key_press':
            isDuplicate =
              last.tabId === step.tabId &&
              (last as any).url === (step as any).url &&
              (last as any).key === (step as any).key &&
              (last as any).xpath === (step as any).xpath;
            break;
        }
      }
      if (isDuplicate) {
        // Update timestamp (and screenshot if present) to most recent but don't add new step
        last.timestamp = step.timestamp;
        if ((step as any).screenshot) {
          (last as any).screenshot = (step as any).screenshot;
        }
      } else {
        allSteps.push(step);
      }
    }

    // Create the workflowData object *after* sorting steps, but hash only steps
    const workflowData: Workflow = {
      name: "Recorded Workflow",
      description: `Recorded on ${new Date().toLocaleString()}`,
      version: "1.0.0",
      input_schema: [],
      steps: allSteps, // allSteps is used here
    };

    const allStepsString = JSON.stringify(allSteps); // Hash based on allSteps
    const currentWorkflowHash = await calculateSHA256(allStepsString);

    // console.log("[DEBUG] broadcastWorkflowDataUpdate: Current steps hash:", currentWorkflowHash, "Last steps hash:", lastWorkflowHash); // Optional

    // Condition to skip logging if the hash of steps is the same
    if (lastWorkflowHash !== null && currentWorkflowHash === lastWorkflowHash) {
      // console.log("[DEBUG] broadcastWorkflowDataUpdate: Steps unchanged, skipping log."); // Optional
      return workflowData;
    }

    lastWorkflowHash = currentWorkflowHash;
    // console.log("[DEBUG] broadcastWorkflowDataUpdate: Steps changed, workflowData object:", JSON.parse(JSON.stringify(workflowData))); // Optional

    // Send workflow update to Python server
    const eventToSend: HttpWorkflowUpdateEvent = {
      type: "WORKFLOW_UPDATE",
      timestamp: Date.now(),
      payload: workflowData,
    };
    sendEventToServer(eventToSend);
    return workflowData;
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
            .catch((err: Error) => {
              // Optional: Log if sending to a specific tab failed (e.g., script not injected)
              // console.debug(`Could not send status to tab ${tab.id}: ${err.message}`);
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
      .catch((err) => {
        // console.debug("Could not send status update to sidepanel (might be closed)", err.message);
      });
  }

  // --- Tab Event Listeners ---

  // Function to send tab events (only if recording is enabled)
  function sendTabEvent(type: string, payload: any) {
    if (!isRecordingEnabled) return;
    console.log(`Sending ${type}:`, payload);
    const tabId = payload.tabId;
    if (tabId) {
      // Skip capturing events for tabs that have never been activated AND are not the original opener
      // unless we have positively identified them as a recent user initiated tab (click intent -> creation).
      if (
        type !== "CUSTOM_TAB_ACTIVATED" &&
        !activatedTabs.has(tabId) &&
        !(payload.openerTabId && recentNewTabIntents[payload.openerTabId] && Date.now() - recentNewTabIntents[payload.openerTabId] < NEW_TAB_INTENT_WINDOW_MS)
      ) {
        // Silently ignore background noise (ad/tracker tabs) until user actually focuses them.
        return;
      }
      if (!sessionLogs[tabId]) {
        sessionLogs[tabId] = [];
      }
      sessionLogs[tabId].push({
        messageType: type,
        timestamp: Date.now(),
        tabId: tabId,
        ...payload,
      });
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
      userInitiated:
        !!(
          tab.openerTabId &&
          recentNewTabIntents[tab.openerTabId] &&
          Date.now() - recentNewTabIntents[tab.openerTabId] < NEW_TAB_INTENT_WINDOW_MS
        ),
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
  activatedTabs.add(activeInfo.tabId);
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

  const DEFAULT_SETTINGS = {
    enableIframes: true as boolean,
    iframeWindow: 3000 as number,
    blocklist: [
      'doubleclick.net','googlesyndication.com','googleadservices.com',
      'amazon-adsystem.com','2mdn.net','recaptcha.google.com','recaptcha.net',
      'googletagmanager.com','indexww.com','adtrafficquality.google','gstaticadssl.googleapis.com'
    ] as string[],
    allowlist: [] as string[],
  };
  let settings: { enableIframes: boolean; iframeWindow: number; blocklist: string[]; allowlist: string[] } = { ...DEFAULT_SETTINGS };
  const settingsReady = new Promise<void>((resolve) => {
    chrome.storage.sync.get(DEFAULT_SETTINGS, (s: any) => {
      settings = { ...DEFAULT_SETTINGS, ...s };
      resolve();
    });
  });
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== 'sync') return;
    const next = { ...settings } as any;
    for (const k of Object.keys(changes)) (next as any)[k] = (changes as any)[k].newValue;
    settings = next;
  });

  function convertStoredEventsToSteps(events: StoredEvent[]): Step[] {
    const steps: Step[] = [];
    const lastNavigationIndexByTab: Record<number, number> = {};
    const lastInputPerKey: Record<string, { idx: number; ts: number; value: string }> = {};

    for (const event of events) {
      switch (event.messageType) {
        case "CUSTOM_TAB_CREATED":
        case "CUSTOM_TAB_UPDATED":
        case "CUSTOM_TAB_ACTIVATED": {
          const navUrl = (event as any).url || (event as any).changeInfo?.url;
          if (!navUrl) break;
          const tabId = (event as any).tabId;
          const userInitiated = (event as any).userInitiated;
          if (!activatedTabs.has(tabId) && !userInitiated) break; // suppress background noise

          const existingIdx = lastNavigationIndexByTab[tabId];
          if (
            existingIdx !== undefined &&
            steps[existingIdx] &&
            steps[existingIdx].type === "navigation"
          ) {
            // Update existing navigation (redirect / title change)
            (steps[existingIdx] as NavigationStep).url = navUrl;
            steps[existingIdx].timestamp = event.timestamp;
          } else {
            const nav: NavigationStep = {
              type: "navigation",
              timestamp: event.timestamp,
              tabId,
              url: navUrl,
            };
            steps.push(nav);
            lastNavigationIndexByTab[tabId] = steps.length - 1;
          }
          break;
        }
        case "CUSTOM_CLICK_EVENT": {
          const click = event as StoredCustomClickEvent;
          if (click.url && click.xpath && click.elementTag) {
            const step: ClickStep = {
              type: "click",
              timestamp: click.timestamp,
              tabId: click.tabId,
              url: click.url,
              frameUrl: click.frameUrl,
              frameIdPath: (click as any).frameIdPath,
              xpath: click.xpath,
              cssSelector: click.cssSelector,
              elementTag: click.elementTag,
              elementText: click.elementText,
              targetText: (click as any).targetText,
              screenshot: click.screenshot,
            };
            steps.push(step);
          } else {
            console.warn("Skipping incomplete CUSTOM_CLICK_EVENT", click);
          }
          break;
        }
        case "CUSTOM_INPUT_EVENT": {
          const inputEvent = event as StoredCustomInputEvent;
          if (inputEvent.url && inputEvent.xpath && inputEvent.elementTag) {
            const key = `${inputEvent.tabId}|${inputEvent.xpath}`;
            const prior = lastInputPerKey[key];
            const nowTs = inputEvent.timestamp;
            const isEmpty = (inputEvent as any).value === "";
            if (isEmpty && prior && prior.value === "" && nowTs - prior.ts < 5000) {
              // collapse rapid-fire repeated empties
              steps[prior.idx].timestamp = nowTs;
              break;
            }
            const lastStep = steps.length > 0 ? steps[steps.length - 1] : null;
            if (
              lastStep &&
              lastStep.type === "input" &&
              lastStep.tabId === inputEvent.tabId &&
              lastStep.url === inputEvent.url &&
              lastStep.frameUrl === inputEvent.frameUrl &&
              lastStep.xpath === inputEvent.xpath &&
              lastStep.cssSelector === inputEvent.cssSelector &&
              lastStep.elementTag === inputEvent.elementTag
            ) {
              (lastStep as InputStep).value = inputEvent.value;
              lastStep.timestamp = inputEvent.timestamp;
              (lastStep as InputStep).screenshot = inputEvent.screenshot;
              lastInputPerKey[key] = { idx: steps.length - 1, ts: nowTs, value: (inputEvent as any).value };
            } else {
              const newStep: InputStep = {
                type: "input",
                timestamp: inputEvent.timestamp,
                tabId: inputEvent.tabId,
                url: inputEvent.url,
                frameUrl: inputEvent.frameUrl,
                frameIdPath: (inputEvent as any).frameIdPath,
                xpath: inputEvent.xpath,
                cssSelector: inputEvent.cssSelector,
                elementTag: inputEvent.elementTag,
                value: inputEvent.value,
                targetText: (inputEvent as any).targetText,
                screenshot: inputEvent.screenshot,
              };
              steps.push(newStep);
              lastInputPerKey[key] = { idx: steps.length - 1, ts: nowTs, value: (inputEvent as any).value };
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
              frameIdPath: (keyEvent as any).frameIdPath,
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
            // Drop internal chrome pages like chrome://newtab/
            if (currentTabInfo?.url?.startsWith('chrome://')) {
              break;
            }
            // Check if the last step added was a mergeable scroll event
            const lastStep = steps.length > 0 ? steps[steps.length - 1] : null;
            if (
              lastStep &&
              lastStep.type === "scroll" &&
              lastStep.tabId === rrEvent.tabId &&
              // Treat same XY within a short time window as duplicate, regardless of targetId
              (lastStep as ScrollStep).scrollX === scrollData.x &&
              (lastStep as ScrollStep).scrollY === scrollData.y &&
              Math.abs(rrEvent.timestamp - lastStep.timestamp) < 200 &&
              (lastStep as any).url === currentTabInfo?.url
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
          } else if (rrEvent.type === EventType.Meta && rrEvent.data?.href) {
            // Also handle rrweb meta events as navigation
            const metaData = rrEvent.data as { href: string };
            const href = metaData.href;
            // Drop about:blank always
            if (href === 'about:blank') {
              break;
            }
            try {
              const urlObj = new URL(href);
              const host = urlObj.hostname;
              // Allowlist overrides blocklist
              const inAllow = settings.allowlist.some(d => host.endsWith(d));
              const inBlock = settings.blocklist.some(d => host.endsWith(d));
              if (!inAllow && inBlock) {
                break;
              }
              if (!settings.enableIframes && !(rrEvent as any).isTopFrame) {
                break; // user disabled iframe recording
              }
              // If top frame, allow
              if ((rrEvent as any).isTopFrame) {
                // allowed
              } else {
                const fUrl = (rrEvent as any).frameUrl as string | undefined;
                if (!fUrl) break;
                const times = interactedFrameTimes[rrEvent.tabId] || {};
                const lastTs = times[fUrl];
                if (!lastTs) break;
                const eventTimestamp = typeof (rrEvent as any).timestamp === "number" ? (rrEvent as any).timestamp : Date.now();
                if (eventTimestamp - lastTs > settings.iframeWindow) break;
              }
            } catch {
              break;
            }
            const step: NavigationStep = {
              type: "navigation",
              timestamp: rrEvent.timestamp,
              tabId: rrEvent.tabId,
              url: metaData.href,
              // frameIdPath could be attached if needed
            };
            steps.push(step);
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
  // Synthetic event we will emit from content script just before an expected new tab open.
  "PREPARE_NEW_TAB",
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

      // Record intent for new tab opening to correlate with onCreated event.
      if (message.type === "PREPARE_NEW_TAB") {
        recentNewTabIntents[sender.tab.id] = Date.now();
        // We do not store this as a workflow step; it's only heuristic metadata.
        return false;
      }

      // Function to store the event
      const storeEvent = (eventPayload: any, screenshotDataUrl?: string) => {
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

        const eventWithMeta = {
          ...eventPayload,
          tabId: tabId,
          messageType: message.type,
          screenshot: screenshotDataUrl,
        };
        sessionLogs[tabId].push(eventWithMeta);
        // Mark frame as interacted so subsequent iframe meta navigations can be allowed
        if (message.type.startsWith("CUSTOM_") && eventPayload.frameUrl) {
          if (!interactedFrameUrls[tabId]) interactedFrameUrls[tabId] = new Set();
          interactedFrameUrls[tabId].add(eventPayload.frameUrl);
          if (!interactedFrameTimes[tabId]) interactedFrameTimes[tabId] = {};
          const interactionTimestamp = typeof eventPayload.timestamp === "number" ? eventPayload.timestamp : Date.now();
          interactedFrameTimes[tabId][eventPayload.frameUrl] = interactionTimestamp;
        }
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
