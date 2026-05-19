import React, { useEffect, useState, useCallback } from "react";
import { Button } from "@/components/ui/button";

interface ConnectionStatus {
  connected: boolean;
  message: string;
  timestamp?: number;
}

export const SettingsView: React.FC = () => {
  const [backendUrl, setBackendUrl] = useState("http://127.0.0.1:8000");
  const [editingUrl, setEditingUrl] = useState("");
  const [isEditing, setIsEditing] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>({
    connected: false,
    message: "Not checked",
  });
  const [testing, setTesting] = useState(false);
  const [saved, setSaved] = useState(false);

  // Load current settings
  useEffect(() => {
    chrome.runtime.sendMessage({ type: "GET_BACKEND_URL" }, (response) => {
      if (response?.url) {
        setBackendUrl(response.url);
        setEditingUrl(response.url);
      }
    });
  }, []);

  const testConnection = useCallback(async () => {
    setTesting(true);
    setConnectionStatus({ connected: false, message: "Testing..." });

    try {
      const response = await chrome.runtime.sendMessage({
        type: "CHECK_BACKEND_HEALTH",
      });

      if (response?.connected) {
        setConnectionStatus({
          connected: true,
          message: `Connected to ${response.data?.service || "backend"}`,
          timestamp: response.data?.timestamp,
        });
      } else {
        setConnectionStatus({
          connected: false,
          message: `Failed: ${response?.error || "Unknown error"}`,
        });
      }
    } catch (error) {
      setConnectionStatus({
        connected: false,
        message: `Error: ${error instanceof Error ? error.message : String(error)}`,
      });
    } finally {
      setTesting(false);
    }
  }, []);

  // Test on mount
  useEffect(() => {
    testConnection();
  }, [testConnection]);

  const saveUrl = () => {
    const trimmed = editingUrl.trim().replace(/\/+$/, ""); // Remove trailing slashes
    if (!trimmed) return;

    chrome.runtime.sendMessage(
      { type: "UPDATE_BACKEND_URL", payload: { url: trimmed } },
      (response) => {
        if (response?.success) {
          setBackendUrl(trimmed);
          setIsEditing(false);
          setSaved(true);
          setTimeout(() => setSaved(false), 2000);
          // Re-test with new URL
          testConnection();
        }
      }
    );
  };

  return (
    <div className="flex flex-col h-full bg-white">
      {/* Header */}
      <div className="p-3 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-900">Settings</h2>
        <p className="text-xs text-gray-500">
          Configure your Workflow Use extension
        </p>
      </div>

      <div className="flex-grow overflow-y-auto p-4 space-y-6">
        {/* Connection Status */}
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-gray-900">
            Backend Connection
          </h3>
          <div
            className={`flex items-center space-x-2 p-3 rounded-lg border ${
              connectionStatus.connected
                ? "bg-green-50 border-green-200"
                : "bg-red-50 border-red-200"
            }`}
          >
            <div
              className={`w-3 h-3 rounded-full flex-shrink-0 ${
                connectionStatus.connected
                  ? "bg-green-500"
                  : "bg-red-500 animate-pulse"
              }`}
            />
            <div className="flex-1">
              <p
                className={`text-xs font-medium ${
                  connectionStatus.connected
                    ? "text-green-700"
                    : "text-red-700"
                }`}
              >
                {connectionStatus.connected ? "Connected" : "Disconnected"}
              </p>
              <p className="text-[10px] text-gray-500">
                {connectionStatus.message}
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={testConnection}
              disabled={testing}
              className="text-xs px-2 py-1 h-7"
            >
              {testing ? "Testing..." : "Test"}
            </Button>
          </div>
        </div>

        {/* Backend URL */}
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-gray-900">Backend URL</h3>
          <p className="text-xs text-gray-500">
            The URL where the workflow-use Python backend is running
          </p>
          {isEditing ? (
            <div className="space-y-2">
              <input
                type="text"
                value={editingUrl}
                onChange={(e) => setEditingUrl(e.target.value)}
                placeholder="http://127.0.0.1:8000"
                className="w-full p-2 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500 font-mono"
              />
              <div className="flex space-x-2">
                <Button
                  size="sm"
                  onClick={saveUrl}
                  className="text-xs px-3 py-1"
                >
                  Save
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setIsEditing(false);
                    setEditingUrl(backendUrl);
                  }}
                  className="text-xs px-3 py-1"
                >
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <div className="flex items-center space-x-2">
              <code className="flex-1 p-2 text-xs bg-gray-50 border border-gray-200 rounded font-mono text-gray-700">
                {backendUrl}
              </code>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsEditing(true)}
                className="text-xs px-3 py-1"
              >
                Edit
              </Button>
            </div>
          )}
          {saved && (
            <p className="text-xs text-green-600 font-medium">
              Settings saved!
            </p>
          )}
        </div>

        {/* Quick Info */}
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-gray-900">Quick Start</h3>
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 space-y-2 text-xs text-gray-600">
            <p>
              <strong>1.</strong> Make sure the Python backend is running:
            </p>
            <code className="block bg-white p-2 rounded border text-[10px] font-mono">
              cd workflows && python cli.py launch-gui
            </code>
            <p>
              <strong>2.</strong> Go to the <strong>Record</strong> tab to start
              recording a workflow
            </p>
            <p>
              <strong>3.</strong> Your recorded workflows appear in the{" "}
              <strong>Workflows</strong> tab
            </p>
          </div>
        </div>

        {/* About */}
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-gray-900">About</h3>
          <div className="text-xs text-gray-500 space-y-1">
            <p>Workflow Use — Browser automation with self-healing</p>
            <p>Phase 2: Standalone Chrome Extension</p>
            <p className="text-[10px] text-gray-400">
              Records in YOUR browser with your credentials
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
