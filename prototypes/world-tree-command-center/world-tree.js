const scrollRoot=document.getElementById('world');
const treeStage=document.getElementById('treeStage');
const activeStratum=document.getElementById('activeStratum');
const drawer=document.getElementById('drawer');
const drawerClose=document.getElementById('drawerClose');
const drawerTitle=document.getElementById('drawerTitle');
const drawerText=document.getElementById('drawerText');
const drawerMetrics=document.getElementById('drawerMetrics');
const drawerEyebrow=document.getElementById('drawerEyebrow');
const railBtns=[...document.querySelectorAll('.rail-btn')];
const nodes={
 'open-notebook':{k:'PRIVATE COGNITIVE CORE',t:'Open Notebook',d:'Local research and synthesis surface hosted on the VPS. Keep proprietary source material private, promote validated outputs into shared memory, and emit evidence receipts.',m:[['PORT','8502'],['MODE','LOCAL'],['RAG','READY'],['VFS','MOUNTED']]},
 notebooklm:{k:'GOVERNED CLOUD BRAIN',t:'NotebookLM Synapse',d:'External synthesis surface linked through an explicit policy boundary. Default posture is read-only with human approval before sensitive material crosses the synapse.',m:[['LINK','SYNCED'],['GATE','HITL'],['POLICY','R/O'],['QUEUE','3']]},
 throne:{k:'EXECUTIVE CONTROL',t:'Throne Room',d:'Top-level CEO command surface. Decrees are routed to the appropriate council agents, checked by governance, then translated into executable missions.',m:[['COUNCIL','18'],['GATES','5/5'],['RISK','LOW'],['STATUS','READY']]},
 'world-api':{k:'SEMANTIC TOPOLOGY',t:'World Tree API',d:'Graph stream that binds services, memories, missions, receipts and agents into one navigable operating model.',m:[['PORT','3006'],['STREAM','SSE'],['NODES','128'],['STATE','LIVE']]},
 vfs:{k:'MEMORY FABRIC',t:'Virtual File System',d:'Attested semantic file layer for memory slabs, refractions, receipts and agent state. This is the bridge between cognitive objects and physical storage.',m:[['ROOT','/vfs'],['ATTEST','PASS'],['LEASES','ACTIVE'],['LAT','0.82ms']]},
 missions:{k:'EXECUTION',t:'Active Missions',d:'Current DAG-backed work moving through Camelot.',m:[['RUNNING','12'],['BLOCKED','1'],['RECEIPTED','34'],['SLA','99.4%']]},
 agents:{k:'COUNCIL',t:'Knights & Mages',d:'Specialized agents available to the solo CEO command plane.',m:[['ACTIVE','18'],['IDLE','4'],['QUAR','0'],['ALIGN','99.6%']]},
 risk:{k:'GOVERNANCE',t:'Enterprise Risk',d:'Consolidated operational, security, resource and policy posture.',m:[['LEVEL','LOW'],['POLICY','PASS'],['RAM','77%'],['ALERTS','2']]}
};
function openDrawer(key){const n=nodes[key]||nodes.vfs;drawerEyebrow.textContent=n.k;drawerTitle.textContent=n.t;drawerText.textContent=n.d;drawerMetrics.innerHTML=n.m.map(([a,b])=>`<span><b>${b}</b>${a}</span>`).join('');drawer.classList.add('open');drawer.setAttribute('aria-hidden','false');drawerClose.focus({preventScroll:true});}
function closeDrawer(){drawer.classList.remove('open');drawer.setAttribute('aria-hidden','true');}
document.querySelectorAll('[data-panel],[data-open]').forEach(el=>el.addEventListener('click',()=>openDrawer(el.dataset.panel||el.dataset.open)));
drawerClose.addEventListener('click',closeDrawer);document.addEventListener('keydown',e=>{if(e.key==='Escape')closeDrawer()});
railBtns.forEach(btn=>btn.addEventListener('click',()=>document.getElementById(btn.dataset.jump).scrollIntoView({behavior:document.body.classList.contains('reduced-motion')?'auto':'smooth'})));
const sections=[...document.querySelectorAll('.stratum')];
const io=new IntersectionObserver(entries=>entries.forEach(entry=>{if(entry.isIntersecting&&entry.intersectionRatio>.38){const id=entry.target.id;activeStratum.textContent=entry.target.dataset.stratum;railBtns.forEach(b=>b.classList.toggle('active',b.dataset.jump===id));}}),{root:scrollRoot,threshold:[.38,.55,.7]});sections.forEach(s=>io.observe(s));
function tilt(clientX,clientY){if(document.body.classList.contains('reduced-motion'))return;const r=treeStage.getBoundingClientRect();const x=(clientX-r.left)/r.width-.5;const y=(clientY-r.top)/r.height-.5;document.documentElement.style.setProperty('--tiltY',`${x*12}deg`);document.documentElement.style.setProperty('--tiltX',`${y*-9}deg`);document.documentElement.style.setProperty('--depth',`${Math.max(0,18-Math.abs(x*20))}px`)}
treeStage.addEventListener('pointermove',e=>tilt(e.clientX,e.clientY));treeStage.addEventListener('pointerleave',()=>{document.documentElement.style.setProperty('--tiltY','0deg');document.documentElement.style.setProperty('--tiltX','0deg');document.documentElement.style.setProperty('--depth','0px')});
let keyX=0,keyY=0;treeStage.addEventListener('keydown',e=>{if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)){e.preventDefault();if(e.key==='ArrowLeft')keyY-=2;if(e.key==='ArrowRight')keyY+=2;if(e.key==='ArrowUp')keyX-=2;if(e.key==='ArrowDown')keyX+=2;keyX=Math.max(-10,Math.min(10,keyX));keyY=Math.max(-14,Math.min(14,keyY));document.documentElement.style.setProperty('--tiltY',keyY+'deg');document.documentElement.style.setProperty('--tiltX',keyX+'deg')}});
document.getElementById('motionToggle').addEventListener('click',e=>{const on=document.body.classList.toggle('reduced-motion');e.currentTarget.setAttribute('aria-pressed',String(on));});
document.querySelectorAll('.folder-tree button').forEach(btn=>btn.addEventListener('click',()=>{document.querySelectorAll('.folder-tree .file').forEach(x=>x.classList.remove('active'));if(btn.classList.contains('file'))btn.classList.add('active')}));
document.querySelectorAll('[data-agent]').forEach(btn=>btn.addEventListener('click',()=>{document.getElementById('decree').value=`Summon ${btn.dataset.agent}: `;document.getElementById('decree').focus()}));
document.getElementById('decreeForm').addEventListener('submit',e=>{e.preventDefault();const input=document.getElementById('decree');const out=document.getElementById('decreeOutput');if(!input.value.trim())return;out.textContent='Routing decree → governance gate → council planner → mission DAG…';setTimeout(()=>out.textContent='DECREE ACCEPTED • mission CAM-'+Math.random().toString(16).slice(2,8).toUpperCase()+' forged • evidence receipt pending',650)});
