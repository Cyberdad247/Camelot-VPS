const fs = require('fs');
const content = fs.readFileSync('src/components/MissionArena.tsx', 'utf-8');

// 1. First, make sure we import ILease and ITaskExecutionRequest from SentinelPolicyEngine
let newContent = content.replace(
  "import { SentinelPolicyEngine } from './SentinelPolicyEngine';",
  "import { SentinelPolicyEngine, ILease, ITaskExecutionRequest } from './SentinelPolicyEngine';"
);

// 2. Add state for activeLeases, showSentinel, and currentRequest
newContent = newContent.replace(
  "const [minimizedAgents, setMinimizedAgents] = useState(false);",
  `const [minimizedAgents, setMinimizedAgents] = useState(false);
  const [showSentinel, setShowSentinel] = useState(false);
  const [activeLeases, setActiveLeases] = useState<ILease[]>([
    {
      leaseId: 'LEASE_SENTINEL_0x1a2b3c',
      agentId: 'sir_codex',
      expiresAt: Date.now() + 1000 * 60 * 60, // Valid for 1 hour
      allowedEffects: ['read_file', 'write_file', 'execute_wasm']
    }
  ]);
  const [currentRequest, setCurrentRequest] = useState<ITaskExecutionRequest | null>(null);`
);

// 3. Replace handleRun with the new one and add handleAuthorize, handleReject
const handleRunRegex = /const handleRun = \(\) => \{([\s\S]*?)z3ProofStatus: requireValidLease \? 'PROVED' \: 'UNSAT'\n    \};\n\n    setTimeout\(\(\) => \{\n      onDispatchMission\?\.\(newMission\);\n      setIsDispatching\(false\);\n      setCustomPrompt\(''\);\n    \}, 1200\);\n  \};/m;

// If the regex doesn't match, we will just use split/replace
const newHandleRun = `const handleRun = () => {
    if (!customPrompt.trim()) return;
    
    // Create execution request
    const request: ITaskExecutionRequest = {
      taskId: \`TASK-\${Math.floor(Math.random() * 90000)}\`,
      agentId: selectedAgent.id,
      requestedEffect: 'execute_wasm', // hardcoded effect for demo
      missionPrompt: customPrompt
    };
    
    setCurrentRequest(request);
    setShowSentinel(true);
  };

  const handleAuthorize = () => {
    setShowSentinel(false);
    setIsDispatching(true);

    const newMission: AgentMission = {
      id: \`MSN-\${Math.floor(1000 + Math.random() * 9000)}\`,
      agentId: selectedAgent.id,
      agentName: selectedAgent.name,
      agentTitle: selectedAgent.title,
      prompt: customPrompt,
      leaseId: requireValidLease ? \`LEASE_SENTINEL_0x\${Math.floor(Math.random() * 0xffffff).toString(16)}\` : 'INVALID_LEASE_0x0000',
      leaseGranted: true,
      status: 'receipted',
      wal2ReceiptHash: \`0x\${Array.from({ length: 32 }, () => Math.floor(Math.random() * 16).toString(16)).join('')}\`,
      executionMs: Number((4 + Math.random() * 12).toFixed(1)),
      resultOutput: \`Execution complete under WASI sandbox. Memory bounded strictly to 64MB. Invariants proved SAT.\`,
      z3ProofStatus: 'PROVED'
    };

    setTimeout(() => {
      onDispatchMission?.(newMission);
      setIsDispatching(false);
      setCustomPrompt('');
    }, 1200);
  };

  const handleReject = (reason: string) => {
    setShowSentinel(false);
    
    // Create a failed mission receipt
    const failedMission: AgentMission = {
      id: \`MSN-\${Math.floor(1000 + Math.random() * 9000)}\`,
      agentId: selectedAgent.id,
      agentName: selectedAgent.name,
      agentTitle: selectedAgent.title,
      prompt: customPrompt,
      leaseId: 'INVALID_LEASE_0x0000',
      leaseGranted: false,
      status: 'rejected',
      wal2ReceiptHash: \`0x\${Array.from({ length: 32 }, () => Math.floor(Math.random() * 16).toString(16)).join('')}\`,
      executionMs: 0,
      resultOutput: \`EXECUTION BLOCKED: \${reason}\`,
      z3ProofStatus: 'UNSAT'
    };
    
    onDispatchMission?.(failedMission);
    setCustomPrompt('');
  };`;

// Let's do a more robust string replacement for handleRun
const handleRunStart = "const handleRun = () => {";
const splitContent = newContent.split(handleRunStart);
if (splitContent.length > 1) {
    const remainingPart = splitContent[1];
    // Find the end of handleRun
    const endOfHandleRun = "}, 1200);\n  };";
    const endSplit = remainingPart.split(endOfHandleRun);
    
    if (endSplit.length > 1) {
        newContent = splitContent[0] + newHandleRun + endSplit.slice(1).join(endOfHandleRun);
    }
}

// 4. Inject SentinelPolicyEngine right after the first <div className="max-w-7xl... ">
newContent = newContent.replace(
  '<div className="max-w-7xl mx-auto p-2 sm:p-4 space-y-4 font-mono">',
  `<div className="max-w-7xl mx-auto p-2 sm:p-4 space-y-4 font-mono">
      {showSentinel && currentRequest && (
        <SentinelPolicyEngine
          request={currentRequest}
          activeLeases={requireValidLease ? activeLeases : []}
          onAuthorize={handleAuthorize}
          onReject={handleReject}
        />
      )}`
);

fs.writeFileSync('src/components/MissionArena.tsx', newContent);
