const fs = require('fs');
const content = fs.readFileSync('src/components/OperatorConsoleHtmx.tsx', 'utf-8');

let newContent = content.replace(
  "import { OmarchyManager, OmarchySystemVitals, SliceMetric } from '../utils/OmarchyManager';",
  "import { OmarchyManager, OmarchySystemVitals, SliceMetric } from '../utils/OmarchyManager';\nimport { BitNetWorker } from './BitNetWorker';"
);

// We need to inject 'bitnet' into the useState
newContent = newContent.replace(
  "const [activeTab, setActiveTab] = useState<'approvals' | 'webgpu' | 'contracts' | 'architecture' | 'adversarial' | 'omarchy'>('approvals');",
  "const [activeTab, setActiveTab] = useState<'approvals' | 'webgpu' | 'contracts' | 'architecture' | 'adversarial' | 'omarchy' | 'bitnet'>('approvals');"
);

// We need to add the tab definition
newContent = newContent.replace(
  "{ id: 'omarchy', label: 'Omarchy Monitor', icon: Server }",
  "{ id: 'omarchy', label: 'Omarchy Monitor', icon: Server },\n          { id: 'bitnet', label: 'Phase 4: BitNet', icon: Zap }"
);

// Add the content block for the new tab right at the end before the last closing div.
// It's safer to just replace the adversarial comment block trick again.
const bitnetTabContent = `
      {/* ================= TAB 7: BITNET TERNARY ================= */}
      {activeTab === 'bitnet' && (
         <BitNetWorker />
      )}
`;

newContent = newContent.replace(
  "{/* ================= TAB 5: ADVERSARIAL TEST SUITE ================= */}",
  bitnetTabContent + "\n      {/* ================= TAB 5: ADVERSARIAL TEST SUITE ================= */}"
);

fs.writeFileSync('src/components/OperatorConsoleHtmx.tsx', newContent);
