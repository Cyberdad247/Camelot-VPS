const fs = require('fs');
const content = fs.readFileSync('src/App.tsx', 'utf-8');
let newContent = content.replace(
  "import { Header } from './components/Header';",
  "import { Header } from './components/Header';\nimport { OmarchyManager } from './utils/OmarchyManager';"
);
newContent = newContent.replace(
  "const [vitals, setVitals] = useState<SystemVitals>(INITIAL_VITALS);",
  "const [vitals, setVitals] = useState<SystemVitals>(INITIAL_VITALS);\n  const [omarchyVitals, setOmarchyVitals] = useState<any>(null);\n  const [omarchySlices, setOmarchySlices] = useState<any[]>([]);\n\n  React.useEffect(() => {\n    const manager = OmarchyManager.getInstance();\n    const unsubscribe = manager.subscribe((newVitals, newSlices) => {\n      setOmarchyVitals(newVitals);\n      setOmarchySlices(newSlices);\n    });\n    return () => {\n      unsubscribe();\n      manager.stopSimulation();\n    };\n  }, []);"
);
fs.writeFileSync('src/App.tsx', newContent);
