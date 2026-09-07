const fs = require('fs');
let content = fs.readFileSync('src/components/MissionArena.tsx', 'utf-8');

// The file currently has:
// const [minimizedAgents, setMinimizedAgents] = useState(false);
//   const [showSentinel, setShowSentinel] = useState(false);
//   const [activeLeases, setActiveLeases] = useState<ILease[]>([
// ...
// const [showSentinel, setShowSentinel] = useState(false);

content = content.replace("  const [showSentinel, setShowSentinel] = useState(false);\n  const [minimizedReceipts", "  const [minimizedReceipts");

fs.writeFileSync('src/components/MissionArena.tsx', content);
