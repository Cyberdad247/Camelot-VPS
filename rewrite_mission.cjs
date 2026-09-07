const fs = require('fs');
let content = fs.readFileSync('src/components/MissionArena.tsx', 'utf-8');

// The original handleRun block to replace:
const handleRunStart = "  const handleRun = () => {";
const handleRunEnd = "    }, 800);\n  };";

const startIdx = content.indexOf(handleRunStart);
const endIdx = content.indexOf(handleRunEnd, startIdx) + handleRunEnd.length;

const newHandleRunBlock = `  const handleRun = () => {
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
      confetti({ particleCount: 25, spread: 60, origin: { y: 0.7 } });
    }, 1200);
  };

  const handleReject = (reason: string) => {
    setShowSentinel(false);
    
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

content = content.substring(0, startIdx) + newHandleRunBlock + content.substring(endIdx);

fs.writeFileSync('src/components/MissionArena.tsx', content);
