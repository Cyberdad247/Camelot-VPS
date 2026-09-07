const fs = require('fs');
const content = fs.readFileSync('src/components/MissionArena.tsx', 'utf-8');

let newContent = content.replace(
  "import React, { useState } from 'react';",
  "import React, { useState } from 'react';\nimport { SentinelPolicyEngine } from './SentinelPolicyEngine';"
);

newContent = newContent.replace(
  "const [minimizedAgents, setMinimizedAgents] = useState(false);",
  "const [minimizedAgents, setMinimizedAgents] = useState(false);\n  const [showSentinel, setShowSentinel] = useState(false);"
);

// We need to replace the `handleRun` method.
newContent = newContent.replace(
  /const handleRun = \(\) => \{\s*if \(\!customPrompt\.trim\(\)\) return;\s*setIsDispatching\(true\);\s*\/\/ Simulate delay for authorization UX\s*setTimeout\(\(\) => \{\s*onDispatchMission\(customPrompt, selectedAgentId, requireValidLease\);\s*setIsDispatching\(false\);\s*setCustomPrompt\(''\);\s*\}, 400\);\s*\};/m,
  `const handleRun = () => {
    if (!customPrompt.trim()) return;
    setShowSentinel(true);
  };

  const handleAuthorize = () => {
    setShowSentinel(false);
    setIsDispatching(true);
    setTimeout(() => {
      onDispatchMission(customPrompt, selectedAgentId, requireValidLease);
      setIsDispatching(false);
      setCustomPrompt('');
    }, 400);
  };

  const handleReject = (reason: string) => {
    setShowSentinel(false);
    // User sees warning in modal, then it closes. Dispatch is cancelled.
  };`
);

// We need to inject the <SentinelPolicyEngine /> just inside the return (
newContent = newContent.replace(
  "return (\n    <div className=\"space-y-4\">",
  "return (\n    <div className=\"space-y-4\">\n      {showSentinel && (\n        <SentinelPolicyEngine\n          missionPrompt={customPrompt}\n          agentId={selectedAgentId}\n          requireValidLease={requireValidLease}\n          onAuthorize={handleAuthorize}\n          onReject={handleReject}\n        />\n      )}"
);

fs.writeFileSync('src/components/MissionArena.tsx', newContent);
