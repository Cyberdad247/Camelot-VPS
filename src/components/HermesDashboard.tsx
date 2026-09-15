import React, { useState } from 'react';
import { 
  Bot, 
  ExternalLink, 
  RefreshCw, 
  Maximize2, 
  Minimize2, 
  Copy, 
  Check, 
  ShieldCheck, 
  Key, 
  User, 
  Terminal, 
  Cpu, 
  Zap, 
  Network, 
  Sparkles, 
  Eye, 
  EyeOff, 
  Server,
  Layers,
  ArrowUpRight,
  Database
} from 'lucide-react';

interface HermesDashboardProps {
  onExecuteCommand?: (cmd: string) => void;
  onNavigateTab?: (tab: string) => void;
}

export const HermesDashboard: React.FC<HermesDashboardProps> = ({ 
  onExecuteCommand,
  onNavigateTab 
}) => {
  const [networkTarget, setNetworkTarget] = useState<'public' | 'tailscale'>('public');
  const [showPassword, setShowPassword] = useState<boolean>(false);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [iframeKey, setIframeKey] = useState<number>(0);
  const [isExpanded, setIsExpanded] = useState<boolean>(false);
  const [activeSubTab, setActiveSubTab] = useState<'embed' | 'api_gateway' | 'omarchy_bridge'>('embed');

  const publicUrl = 'http://162.35.107.134/';
  const tailscaleUrl = 'http://100.110.180.18/';
  const currentUrl = networkTarget === 'public' ? publicUrl : tailscaleUrl;
  const apiGatewayUrl = networkTarget === 'public' ? 'http://162.35.107.134/api/v1' : 'http://100.110.180.18/api/v1';

  const handleCopy = (text: string, keyName: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(keyName);
    setTimeout(() => {
      setCopiedKey(null);
    }, 2000);
  };

  const handleReloadFrame = () => {
    setIframeKey(prev => prev + 1);
  };

  return (
    <div className={`space-y-4 font-sans ${isExpanded ? 'fixed inset-0 z-50 bg-[#040711] p-4 overflow-y-auto' : 'p-2 sm:p-4'}`}>
      
      {/* Top Banner & Control Deck */}
      <div className="bg-[#080d1a]/95 border-2 border-[#D4AF37]/40 rounded-2xl p-4 shadow-[0_0_30px_rgba(212,175,55,0.15)] backdrop-blur-xl">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          
          {/* Left: Identity */}
          <div className="flex items-center gap-3.5">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-[#2E0854] via-[#120f26] to-[#0a1428] border-2 border-[#D4AF37] flex items-center justify-center text-[#D4AF37] shadow-[0_0_20px_rgba(212,175,55,0.3)]">
              <Bot className="w-6 h-6 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h1 className="font-heraldic text-lg sm:text-xl font-bold tracking-wider text-white flex items-center gap-2">
                  Hermes Agent <span className="text-[#D4AF37] font-sans font-semibold">Dashboard</span>
                </h1>
                <span className="px-2 py-0.5 text-[9px] uppercase font-mono font-bold tracking-wider rounded bg-[#2E0854]/90 text-[#D4AF37] border border-[#D4AF37]/50 shadow-[0_0_8px_rgba(212,175,55,0.25)]">
                  NOUS RESEARCH // AUTONOMOUS
                </span>
                <span className="px-2 py-0.5 text-[9px] uppercase font-mono font-bold tracking-wider rounded bg-emerald-950/80 text-emerald-300 border border-emerald-500/40 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping"></span>
                  ONLINE (:80 / :9119)
                </span>
              </div>
              <p className="text-[11px] text-slate-400 font-mono flex items-center gap-2 mt-0.5 flex-wrap">
                <span className="text-[#D4AF37]">HERMES_PRIME</span>
                <span className="text-slate-600">•</span>
                <span>OpenAI Gateway: <span className="text-cyan-300 font-mono">:8642</span></span>
                <span className="text-slate-600">•</span>
                <span>Cgroup Limit: <span className="text-amber-400">768MB</span></span>
                <span className="text-slate-600">•</span>
                <span className="text-emerald-400">Groq 14-Model Lattice Ready</span>
              </p>
            </div>
          </div>

          {/* Right: Network Route Selector & Direct Launch */}
          <div className="flex items-center gap-2.5 flex-wrap">
            {/* IP Switcher */}
            <div className="flex items-center bg-[#050b18] border border-cyan-900/60 rounded-xl p-1 font-mono text-xs">
              <button
                onClick={() => setNetworkTarget('public')}
                className={`px-3 py-1 rounded-lg transition-all flex items-center gap-1.5 ${
                  networkTarget === 'public'
                    ? 'bg-[#D4AF37] text-black font-bold shadow-[0_0_10px_rgba(212,175,55,0.4)]'
                    : 'text-slate-400 hover:text-white'
                }`}
                title="Route via Public IPv4 (162.35.107.134)"
              >
                <Network className="w-3.5 h-3.5" />
                <span>Public IPv4</span>
              </button>
              <button
                onClick={() => setNetworkTarget('tailscale')}
                className={`px-3 py-1 rounded-lg transition-all flex items-center gap-1.5 ${
                  networkTarget === 'tailscale'
                    ? 'bg-cyan-500 text-black font-bold shadow-[0_0_10px_rgba(6,182,212,0.4)]'
                    : 'text-slate-400 hover:text-white'
                }`}
                title="Route via Tailscale Mesh (100.110.180.18)"
              >
                <ShieldCheck className="w-3.5 h-3.5" />
                <span>Tailscale Mesh</span>
              </button>
            </div>

            {/* Reload Frame Button */}
            <button
              onClick={handleReloadFrame}
              className="p-2 rounded-xl bg-slate-900 border border-cyan-800/40 text-cyan-300 hover:bg-cyan-950 transition-all"
              title="Reload Frame"
            >
              <RefreshCw className="w-4 h-4" />
            </button>

            {/* Expand / Minimize */}
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="p-2 rounded-xl bg-slate-900 border border-cyan-800/40 text-cyan-300 hover:bg-cyan-950 transition-all"
              title={isExpanded ? 'Restore window size' : 'Expand full screen'}
            >
              {isExpanded ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
            </button>

            {/* Direct Window Launch */}
            <a
              href={currentUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#D4AF37] hover:bg-[#c49f2e] text-black font-bold text-xs font-mono shadow-[0_0_20px_rgba(212,175,55,0.4)] transition-all active:scale-95"
            >
              <span>Launch Hermes UI</span>
              <ArrowUpRight className="w-4 h-4" />
            </a>
          </div>
        </div>

        {/* Sub-tab Navigation */}
        <div className="flex items-center gap-2 mt-4 pt-3 border-t border-cyan-950/80 font-mono text-xs">
          <button
            onClick={() => setActiveSubTab('embed')}
            className={`px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition-all ${
              activeSubTab === 'embed'
                ? 'bg-cyan-950/80 border border-cyan-400 text-cyan-300 shadow-[0_0_12px_rgba(34,211,238,0.2)]'
                : 'text-slate-400 hover:text-slate-200 bg-slate-900/40'
            }`}
          >
            <Server className="w-3.5 h-3.5 text-cyan-400" />
            <span>Interactive WebUI Frame</span>
          </button>
          <button
            onClick={() => setActiveSubTab('api_gateway')}
            className={`px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition-all ${
              activeSubTab === 'api_gateway'
                ? 'bg-purple-950/80 border border-[#D4AF37] text-[#D4AF37] shadow-[0_0_12px_rgba(212,175,55,0.2)]'
                : 'text-slate-400 hover:text-slate-200 bg-slate-900/40'
            }`}
          >
            <Zap className="w-3.5 h-3.5 text-[#D4AF37]" />
            <span>OpenAI API Gateway (:8642)</span>
          </button>
          <button
            onClick={() => setActiveSubTab('omarchy_bridge')}
            className={`px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition-all ${
              activeSubTab === 'omarchy_bridge'
                ? 'bg-emerald-950/80 border border-emerald-500 text-emerald-300 shadow-[0_0_12px_rgba(16,185,129,0.2)]'
                : 'text-slate-400 hover:text-slate-200 bg-slate-900/40'
            }`}
          >
            <Layers className="w-3.5 h-3.5 text-emerald-400" />
            <span>Omarchy Cartridge Bridge</span>
          </button>
        </div>
      </div>

      {/* Access Credentials & Telemetry Cockpit */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
        
        {/* Card 1: Dashboard Login */}
        <div className="bg-[#070b16]/90 border border-[#D4AF37]/30 rounded-xl p-3.5 backdrop-blur-md">
          <div className="flex items-center justify-between text-xs text-[#D4AF37] font-mono mb-2">
            <span className="flex items-center gap-1.5 font-bold uppercase">
              <User className="w-3.5 h-3.5" />
              WebUI Credentials
            </span>
            <span className="text-[10px] text-slate-400">HTTP Basic / Form</span>
          </div>
          <div className="space-y-2 font-mono text-xs">
            <div className="flex items-center justify-between bg-black/50 p-2 rounded border border-slate-800">
              <span className="text-slate-400">User:</span>
              <div className="flex items-center gap-1.5">
                <span className="text-cyan-300 font-bold">admin</span>
                <button
                  onClick={() => handleCopy('admin', 'user')}
                  className="p-1 hover:text-[#D4AF37] transition-all"
                  title="Copy username"
                >
                  {copiedKey === 'user' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5 text-slate-500" />}
                </button>
              </div>
            </div>
            <div className="flex items-center justify-between bg-black/50 p-2 rounded border border-slate-800">
              <span className="text-slate-400">Pass:</span>
              <div className="flex items-center gap-1.5">
                <span className="text-amber-300 font-bold tracking-wider">
                  {showPassword ? 'Rodimu$prime247' : '••••••••••••••'}
                </span>
                <button
                  onClick={() => setShowPassword(!showPassword)}
                  className="p-1 hover:text-white text-slate-500 transition-all"
                  title={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                </button>
                <button
                  onClick={() => handleCopy('Rodimu$prime247', 'pass')}
                  className="p-1 hover:text-[#D4AF37] transition-all"
                  title="Copy password"
                >
                  {copiedKey === 'pass' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5 text-slate-500" />}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Card 2: OpenAI API Gateway */}
        <div className="bg-[#070b16]/90 border border-cyan-800/40 rounded-xl p-3.5 backdrop-blur-md">
          <div className="flex items-center justify-between text-xs text-cyan-400 font-mono mb-2">
            <span className="flex items-center gap-1.5 font-bold uppercase">
              <Zap className="w-3.5 h-3.5" />
              API Gateway Base URL
            </span>
            <span className="text-[10px] text-emerald-400 font-bold">ACTIVE</span>
          </div>
          <div className="bg-black/50 p-2 rounded border border-slate-800 font-mono text-xs flex items-center justify-between">
            <span className="text-cyan-300 truncate max-w-[200px]" title={apiGatewayUrl}>
              {apiGatewayUrl}
            </span>
            <button
              onClick={() => handleCopy(apiGatewayUrl, 'gateway')}
              className="p-1 hover:text-cyan-400 transition-all"
              title="Copy API Gateway URL"
            >
              {copiedKey === 'gateway' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5 text-slate-500" />}
            </button>
          </div>
          <div className="mt-2 text-[10px] text-slate-400 font-mono flex items-center justify-between">
            <span>Auth: Bearer / Root Creds</span>
            <span className="text-[#D4AF37]">OpenAI Spec v1</span>
          </div>
        </div>

        {/* Card 3: SSH Baremetal Hook */}
        <div className="bg-[#070b16]/90 border border-purple-800/40 rounded-xl p-3.5 backdrop-blur-md">
          <div className="flex items-center justify-between text-xs text-purple-300 font-mono mb-2">
            <span className="flex items-center gap-1.5 font-bold uppercase">
              <Terminal className="w-3.5 h-3.5" />
              Passwordless SSH
            </span>
            <span className="text-[10px] text-emerald-400 font-bold">ED25519 OK</span>
          </div>
          <div className="bg-black/50 p-2 rounded border border-slate-800 font-mono text-xs flex items-center justify-between">
            <span className="text-purple-300 truncate font-mono">ssh root@162.35.107.134</span>
            <button
              onClick={() => handleCopy('ssh root@162.35.107.134', 'ssh')}
              className="p-1 hover:text-purple-300 transition-all"
              title="Copy SSH Command"
            >
              {copiedKey === 'ssh' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5 text-slate-500" />}
            </button>
          </div>
          <div className="mt-2 text-[10px] text-slate-400 font-mono flex items-center justify-between">
            <span>Key: ~/.ssh/camelot_oci_ed25519</span>
            <span className="text-emerald-400 font-bold">KVM563</span>
          </div>
        </div>

        {/* Card 4: Docker CLI & Groq Models */}
        <div className="bg-[#070b16]/90 border border-emerald-800/40 rounded-xl p-3.5 backdrop-blur-md">
          <div className="flex items-center justify-between text-xs text-emerald-400 font-mono mb-2">
            <span className="flex items-center gap-1.5 font-bold uppercase">
              <Cpu className="w-3.5 h-3.5" />
              Model Orchestration
            </span>
            <span className="text-[10px] text-[#D4AF37] font-bold">14 GROQ MODELS</span>
          </div>
          <div className="bg-black/50 p-2 rounded border border-slate-800 font-mono text-xs flex items-center justify-between">
            <span className="text-emerald-300 truncate font-mono">docker exec -it hermes hermes model</span>
            <button
              onClick={() => handleCopy('docker exec -it hermes hermes model', 'model_cmd')}
              className="p-1 hover:text-emerald-300 transition-all"
              title="Copy Model Command"
            >
              {copiedKey === 'model_cmd' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5 text-slate-500" />}
            </button>
          </div>
          <div className="mt-2 text-[10px] text-slate-400 font-mono flex items-center justify-between">
            <span>Credentials: /root/hermesagent-credentials.txt</span>
          </div>
        </div>

      </div>

      {/* Main View Area */}
      {activeSubTab === 'embed' && (
        <div className="bg-[#050914] border-2 border-[#D4AF37]/30 rounded-2xl overflow-hidden shadow-2xl flex flex-col min-h-[620px]">
          {/* Frame Header Bar */}
          <div className="bg-[#080e1c] px-4 py-2 border-b border-cyan-900/60 flex items-center justify-between font-mono text-xs">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse"></span>
              <span className="text-slate-300 font-bold">LIVE FRAME:</span>
              <span className="text-[#D4AF37]">{currentUrl}</span>
            </div>
            <div className="flex items-center gap-3 text-slate-400 text-[11px]">
              <span className="hidden sm:inline">If browser restricts HTTP iframe embedding, click:</span>
              <a
                href={currentUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-[#D4AF37] hover:underline font-bold"
              >
                <span>Open in Window</span>
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          </div>

          {/* Iframe Container */}
          <div className="relative flex-1 w-full min-h-[580px] bg-[#02050b]">
            <iframe
              key={iframeKey}
              src={currentUrl}
              title="Hermes Agent Dashboard"
              className="w-full h-full min-h-[580px] border-0"
              sandbox="allow-same-origin allow-scripts allow-forms allow-popups allow-modals"
            />
          </div>
        </div>
      )}

      {/* API Gateway View */}
      {activeSubTab === 'api_gateway' && (
        <div className="bg-[#080d1a] border border-[#D4AF37]/40 rounded-2xl p-6 space-y-4 font-mono text-xs">
          <div className="flex items-center justify-between border-b border-cyan-900/60 pb-3">
            <div>
              <h3 className="text-base font-bold text-white font-heraldic flex items-center gap-2">
                <Zap className="w-5 h-5 text-[#D4AF37]" />
                OpenAI-Compatible REST Gateway
              </h3>
              <p className="text-slate-400 text-xs">
                Interact with the autonomous Hermes Agent layer using standard OpenAI SDK or cURL commands.
              </p>
            </div>
            <span className="px-3 py-1 rounded-full bg-purple-950 border border-purple-500 text-purple-300 font-bold text-[10px]">
              PORT :8642 (REVERSED VIA CADDY)
            </span>
          </div>

          <div className="space-y-3">
            <h4 className="text-slate-300 font-bold uppercase tracking-wider text-[11px] text-[#D4AF37]">
              Sample cURL Request (Models Endpoint)
            </h4>
            <div className="bg-black/70 p-4 rounded-xl border border-slate-800 text-cyan-300 relative">
              <button
                onClick={() => handleCopy(`curl ${apiGatewayUrl}/models \\
  -H "Authorization: Bearer $(ssh root@162.35.107.134 'cat /root/hermesagent-credentials.txt | grep API | cut -d: -f2')"`, 'curl_cmd')}
                className="absolute top-3 right-3 p-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300"
                title="Copy cURL command"
              >
                {copiedKey === 'curl_cmd' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              </button>
              <pre className="overflow-x-auto whitespace-pre">
{`curl ${apiGatewayUrl}/models \\
  -H "Authorization: Bearer <API_BEARER_TOKEN>"`}
              </pre>
            </div>

            <h4 className="text-slate-300 font-bold uppercase tracking-wider text-[11px] text-[#D4AF37] pt-2">
              Python OpenAI SDK Client Configuration
            </h4>
            <div className="bg-black/70 p-4 rounded-xl border border-slate-800 text-emerald-300 relative">
              <button
                onClick={() => handleCopy(`from openai import OpenAI

client = OpenAI(
    base_url="${apiGatewayUrl}",
    api_key="your-hermes-bearer-token"
)

response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[{"role": "user", "content": "Hermes, report status."}]
)
print(response.choices[0].message.content)`, 'py_cmd')}
                className="absolute top-3 right-3 p-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300"
                title="Copy Python snippet"
              >
                {copiedKey === 'py_cmd' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              </button>
              <pre className="overflow-x-auto whitespace-pre">
{`from openai import OpenAI

client = OpenAI(
    base_url="${apiGatewayUrl}",
    api_key="your-hermes-bearer-token"
)

response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[{"role": "user", "content": "Hermes, report status."}]
)
print(response.choices[0].message.content)`}
              </pre>
            </div>
          </div>
        </div>
      )}

      {/* Omarchy Cartridge Bridge View */}
      {activeSubTab === 'omarchy_bridge' && (
        <div className="bg-[#080d1a] border border-emerald-500/40 rounded-2xl p-6 space-y-4 font-mono text-xs">
          <div className="flex items-center justify-between border-b border-cyan-900/60 pb-3">
            <div>
              <h3 className="text-base font-bold text-white font-heraldic flex items-center gap-2">
                <Layers className="w-5 h-5 text-emerald-400" />
                Omarchy Cartridge: <span className="text-[#D4AF37]">omarchy-vps-hermes-v1</span>
              </h3>
              <p className="text-slate-400 text-xs">
                Sovereign architectural assimilation receipt: <span className="text-emerald-300">asm_bd835c11f0</span> (Anya Gate Sealed).
              </p>
            </div>
            <span className="px-3 py-1 rounded-full bg-emerald-950 border border-emerald-500 text-emerald-300 font-bold text-[10px]">
              VERIFIED 0% GUI // 100% HEADLESS
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="bg-black/50 p-3.5 rounded-xl border border-slate-800 space-y-1.5">
              <span className="text-slate-400 font-bold uppercase text-[10px]">RAM Footprint</span>
              <div className="text-lg font-bold text-cyan-300">918 MB / 7,941 MB</div>
              <p className="text-[10px] text-slate-500">Zero GUI leaks, cgroups v2 strict containment</p>
            </div>
            <div className="bg-black/50 p-3.5 rounded-xl border border-slate-800 space-y-1.5">
              <span className="text-slate-400 font-bold uppercase text-[10px]">Core Dump Sentinel</span>
              <div className="text-lg font-bold text-emerald-400">0 Segfaults (Healthy)</div>
              <p className="text-[10px] text-slate-500">Autonomous coredump monitoring daemon</p>
            </div>
            <div className="bg-black/50 p-3.5 rounded-xl border border-slate-800 space-y-1.5">
              <span className="text-slate-400 font-bold uppercase text-[10px]">Swarm Matrix</span>
              <div className="text-lg font-bold text-[#D4AF37]">4 Agents Harmonized</div>
              <p className="text-[10px] text-slate-500">Boris, Codex, Sir Helios, Lakisha &rarr; Hermes Bridge</p>
            </div>
          </div>

          <div className="bg-black/60 p-3 rounded-xl border border-cyan-900/40 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Database className="w-4 h-4 text-cyan-400" />
              <span className="text-slate-300">Run Omarchy Headless Verifier:</span>
              <code className="text-cyan-300 bg-slate-900 px-2 py-0.5 rounded">python control_plane/runners/omarchy_headless_verifier.py</code>
            </div>
            <button
              onClick={() => onExecuteCommand && onExecuteCommand('python control_plane/runners/omarchy_headless_verifier.py')}
              className="px-3 py-1 rounded bg-cyan-600 hover:bg-cyan-500 text-black font-bold text-[10px]"
            >
              Run Audit
            </button>
          </div>
        </div>
      )}

    </div>
  );
};
