import React from 'react';

export const Welcome = () => {
  return (
    <div className="flex flex-col items-center justify-center h-full p-8">
      <h1 className="text-4xl font-bold text-gray-800 mb-6">
        Welcome to Browser-Use Workflows
      </h1>
      <p className="text-lg text-gray-600">
        Choose a workflow from the sidebar to get started
      </p>
    </div>
  );
};
