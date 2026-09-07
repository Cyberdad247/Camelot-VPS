const fs = require('fs');
const content = fs.readFileSync('src/components/OperatorConsoleHtmx.tsx', 'utf-8');

let newContent = content.replace(
  "import React, { useState, useEffect, useRef } from 'react';",
  "import React, { useState, useEffect, useRef } from 'react';\nimport { OmarchyManager, OmarchySystemVitals, SliceMetric } from '../utils/OmarchyManager';"
);

// Add the state variables inside the component
newContent = newContent.replace(
  "const [activeTab, setActiveTab] = useState<'approvals' | 'webgpu' | 'contracts' | 'architecture' | 'adversarial'>('approvals');",
  "const [activeTab, setActiveTab] = useState<'approvals' | 'webgpu' | 'contracts' | 'architecture' | 'adversarial' | 'omarchy'>('approvals');\n  const [omarchyVitals, setOmarchyVitals] = useState<OmarchySystemVitals | null>(null);\n  const [omarchySlices, setOmarchySlices] = useState<SliceMetric[]>([]);\n\n  useEffect(() => {\n    const manager = OmarchyManager.getInstance();\n    const unsubscribe = manager.subscribe((vitals, slices) => {\n      setOmarchyVitals(vitals);\n      setOmarchySlices(slices);\n    });\n    return () => unsubscribe();\n  }, []);"
);

// Add the new tab button
newContent = newContent.replace(
  "{ id: 'adversarial', label: 'Adversarial Gauntlet', icon: ShieldCheck }",
  "{ id: 'adversarial', label: 'Adversarial Gauntlet', icon: ShieldCheck },\n          { id: 'omarchy', label: 'Omarchy Monitor', icon: Server }"
);

// Add the new tab content
const omarchyTabContent = `
      {/* ================= TAB 6: OMARCHY MANAGER ================= */}
      {activeTab === 'omarchy' && omarchyVitals && (
        <div className="space-y-4">
          <div className="p-4 rounded-2xl bg-[#090d18] border border-cyan-500/40 space-y-3">
            <h3 className="text-sm font-bold text-cyan-300 flex items-center gap-2">
              <Server className="w-4 h-4 text-cyan-400" />
              <span>OMARCHY BAREMETAL HOST METRICS (8GB LIMIT)</span>
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-3 bg-black border border-slate-800 rounded-xl">
                <div className="text-[10px] text-slate-500 mb-1 font-mono">CPU USAGE</div>
                <div className="text-lg text-emerald-400 font-bold">{omarchyVitals.cpuUsage.toFixed(1)}%</div>
              </div>
              <div className="p-3 bg-black border border-slate-800 rounded-xl">
                <div className="text-[10px] text-slate-500 mb-1 font-mono">MEMORY (USED / LIMIT)</div>
                <div className="text-lg text-cyan-400 font-bold">{omarchyVitals.memoryUsed} <span className="text-sm text-slate-500">/ {omarchyVitals.memoryLimit} MB</span></div>
              </div>
              <div className="p-3 bg-black border border-slate-800 rounded-xl">
                <div className="text-[10px] text-slate-500 mb-1 font-mono">CGROUP SLICES</div>
                <div className="text-lg text-luxora font-bold">{omarchyVitals.activeSlices} ACTIVE</div>
              </div>
              <div className="p-3 bg-black border border-slate-800 rounded-xl">
                <div className="text-[10px] text-slate-500 mb-1 font-mono">STATUS</div>
                <div className={\`text-lg font-bold \${omarchyVitals.status === 'NOMINAL' ? 'text-emerald-400' : 'text-red-500'}\`}>{omarchyVitals.status}</div>
              </div>
            </div>
          </div>
          
          <div className="p-4 rounded-2xl bg-black border border-slate-800 space-y-3">
             <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest">SYSTEMD SLICE ALLOCATIONS</h3>
             <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
               {omarchySlices.map((slice, i) => (
                 <div key={i} className="p-3 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs">
                   <div className="flex justify-between items-center border-b border-slate-800 pb-2 mb-2">
                     <span className="text-cyan-300 font-bold">{slice.name}</span>
                     <span className="text-emerald-400">{slice.status}</span>
                   </div>
                   <div className="flex justify-between text-slate-400">
                     <span>Current Mem:</span>
                     <span className="text-white">{slice.memoryCurrent}</span>
                   </div>
                   <div className="flex justify-between text-slate-400">
                     <span>Limit:</span>
                     <span className="text-luxora">{slice.memoryLimit}</span>
                   </div>
                   <div className="flex justify-between text-slate-400 mt-1">
                     <span>Tasks:</span>
                     <span className="text-white">{slice.tasks}</span>
                   </div>
                 </div>
               ))}
             </div>
          </div>
        </div>
      )}
`;

newContent = newContent.replace(
  "{/* ================= TAB 5: ADVERSARIAL TEST SUITE ================= */}",
  omarchyTabContent + "\n      {/* ================= TAB 5: ADVERSARIAL TEST SUITE ================= */}"
);

fs.writeFileSync('src/components/OperatorConsoleHtmx.tsx', newContent);
