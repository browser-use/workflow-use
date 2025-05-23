import React from 'react';

const NoWorkflowsMessage: React.FC = () => {
  return (
    <div className="flex flex-col justify-center items-center h-screen bg-[#2a2a2a] text-white p-0 px-5 text-center">
      <img 
        src="/browseruse.png" 
        alt="Browser Use Logo" 
        className="w-[150px] h-auto mb-[30px]"
      />
      <h2 className="text-xl mb-[10px]">No Workflows Found</h2>
      <p className="text-sm max-w-[500px] leading-normal mb-[10px]">
        To get started with Workflow Use, you need to first create a workflow 
        or place an existing workflow file in the <code>workflows/tmp</code> folder.
      </p>
      <p className="text-sm max-w-[450px] leading-normal mb-[30px]">
        Once you've added a workflow file, refresh this page to visualize and interact with it. For more information, checkout out the documentation below.
      </p>
      <a 
        href="https://github.com/browser-use/workflow-use" 
        target="_blank" 
        rel="noopener noreferrer"
        className="inline-block bg-blue-400 hover:bg-blue-500 text-white no-underline py-[10px] px-[20px] rounded font-bold text-base transition-colors"
      >
        Learn More
      </a>
    </div>
  );
};

export default NoWorkflowsMessage;
