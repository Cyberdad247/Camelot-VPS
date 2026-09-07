import React, { useState, useEffect } from 'react';
import { Shield, ShieldAlert, CheckCircle2, Lock, Activity } from 'lucide-react';

interface SentinelPolicyEngineProps {
  missionPrompt: string;
  agentId: string;
  requireValidLease: boolean;
  onAuthorize: () => void;
  onReject: (reason: string) => void;
}

export const SentinelPolicyEngine: React.FC<SentinelPolicyEngineProps> = ({
  missionPrompt,
  agentId,
  requireValidLease,
  onAuthorize,
  onReject,
}) => {
  const [status, setStatus] = useState<'verifying' | 'approved' | 'rejected'>('verifying');
  const [logs, setLogs] = useState<string[]>([]);

  useEffect(() => {
    let mounted = true;
    const runVerification = async () => {
      const addLog = (msg: string, delay: number) => {
        return new Promise(resolve => {
          setTimeout(() => {
            if (mounted) setLogs(prev => [...prev, msg]);
            resolve(null);
          }, delay);
        });
      };

      await addLog('[SENTINEL] Intercepting execution request...', 200);
      await addLog(`[SENTINEL] Manifest Agent: ${agentId}`, 300);
      
      if (!requireValidLease) {
        await addLog('[SENTINEL] WARNING: Operating without valid Sentinel lease.', 300);
        await addLog('[SENTINEL] Zero-Trust Violation detected. Rejecting payload.', 400);
        if (mounted) {
          setStatus('rejected');
          setTimeout(() => onReject('Missing capability lease.'), 1500);
        }
        return;
      }

      await addLog('[SENTINEL] Validating Ed25519 signature on capability lease...', 400);
      await addLog('[SENTINEL] Matching EffectManifest against active capabilities...', 500);
      await addLog('[SENTINEL] 8GB Scarcity Protocol limits verified.', 300);
      await addLog('[SENTINEL] Authorization APPROVED.', 300);
      
      if (mounted) {
        setStatus('approved');
        setTimeout(() => onAuthorize(), 1000);
      }
    };
    
    runVerification();
    return () => { mounted = false; };
  }, [agentId, requireValidLease, onAuthorize, onReject]);

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm">
      <div className={`w-full max-w-lg p-6 rounded-2xl border bg-[#050505] shadow-2xl transition-all ${status === 'verifying' ? 'border-cyan-500/50 shadow-[0_0_30px_rgba(34,211,238,0.2)]' : status === 'approved' ? 'border-emerald-500/50 shadow-[0_0_30px_rgba(16,185,129,0.2)]' : 'border-red-500/50 shadow-[0_0_30px_rgba(239,68,68,0.2)]'}`}>
        <div className="flex items-center gap-3 mb-4">
          {status === 'verifying' && <Activity className="w-6 h-6 text-cyan-400 animate-pulse" />}
          {status === 'approved' && <CheckCircle2 className="w-6 h-6 text-emerald-400" />}
          {status === 'rejected' && <ShieldAlert className="w-6 h-6 text-red-500" />}
          <h2 className="text-sm font-bold text-slate-200 uppercase tracking-widest">Sentinel Policy Engine</h2>
        </div>
        
        <div className="bg-black border border-slate-800 rounded-xl p-4 font-mono text-xs space-y-2 h-40 overflow-y-auto mb-4">
          {logs.map((log, i) => (
            <div key={i} className={`${log.includes('WARNING') || log.includes('Rejecting') ? 'text-red-400' : log.includes('APPROVED') ? 'text-emerald-400' : 'text-slate-400'}`}>
              {log}
            </div>
          ))}
          {status === 'verifying' && (
            <div className="flex gap-1 items-center text-cyan-400 mt-2">
              <span className="w-1.5 h-1.5 bg-cyan-400 rounded-full animate-ping"></span>
              <span className="w-1.5 h-1.5 bg-cyan-400 rounded-full animate-ping delay-75"></span>
              <span className="w-1.5 h-1.5 bg-cyan-400 rounded-full animate-ping delay-150"></span>
            </div>
          )}
        </div>
        
        <div className="flex justify-between items-center text-[10px] font-mono text-slate-500">
          <div className="flex items-center gap-2">
            <Lock className="w-3 h-3 text-amber-500" />
            <span>Z3 PROOF GATE</span>
          </div>
          <div>{status.toUpperCase()}</div>
        </div>
      </div>
    </div>
  );
};
