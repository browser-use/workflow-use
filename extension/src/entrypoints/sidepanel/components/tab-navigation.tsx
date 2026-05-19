import React from "react";

export type TabId = "dashboard" | "record" | "settings";

interface TabNavigationProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
  backendConnected: boolean;
}

const tabs: { id: TabId; label: string; icon: string }[] = [
  { id: "dashboard", label: "Workflows", icon: "📋" },
  { id: "record", label: "Record", icon: "🔴" },
  { id: "settings", label: "Settings", icon: "⚙️" },
];

export const TabNavigation: React.FC<TabNavigationProps> = ({
  activeTab,
  onTabChange,
  backendConnected,
}) => {
  return (
    <div className="flex items-center border-b border-gray-200 bg-white px-1">
      {/* Connection indicator */}
      <div
        className="flex items-center px-2 py-2"
        title={backendConnected ? "Backend connected" : "Backend disconnected"}
      >
        <div
          className={`w-2 h-2 rounded-full ${
            backendConnected ? "bg-green-500" : "bg-red-500 animate-pulse"
          }`}
        />
      </div>

      {/* Tabs */}
      <div className="flex flex-1">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            className={`flex items-center space-x-1.5 px-3 py-2.5 text-xs font-medium border-b-2 transition-colors ${
              activeTab === tab.id
                ? "border-blue-500 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
            }`}
          >
            <span>{tab.icon}</span>
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Brand */}
      <div className="px-2 text-[10px] text-gray-400 font-medium">
        WF-Use
      </div>
    </div>
  );
};
