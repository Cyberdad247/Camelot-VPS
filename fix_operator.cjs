const fs = require('fs');
let content = fs.readFileSync('src/components/OperatorConsoleHtmx.tsx', 'utf-8');

// I need to add omarchyVitals and omarchySlices state variables back because they were overwritten somehow
content = content.replace(
  "const [activeTab, setActiveTab] = useState<'approvals' | 'contracts' | 'webgpu' | 'architecture' | 'adversarial'>('approvals');",
  "const [activeTab, setActiveTab] = useState<'approvals' | 'contracts' | 'webgpu' | 'architecture' | 'adversarial' | 'omarchy' | 'bitnet'>('approvals');\n  const [omarchyVitals, setOmarchyVitals] = useState<OmarchySystemVitals | null>(null);\n  const [omarchySlices, setOmarchySlices] = useState<SliceMetric[]>([]);\n\n  useEffect(() => {\n    const manager = OmarchyManager.getInstance();\n    const unsubscribe = manager.subscribe((vitals, slices) => {\n      setOmarchyVitals(vitals);\n      setOmarchySlices(slices);\n    });\n    return () => unsubscribe();\n  }, []);"
);

fs.writeFileSync('src/components/OperatorConsoleHtmx.tsx', content);
