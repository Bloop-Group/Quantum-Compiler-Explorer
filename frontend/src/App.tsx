import { useEffect, useState } from 'react';
import Editor from '@monaco-editor/react';
import { Cpu, Link2, RotateCcw } from 'lucide-react';
import { PRESET_CIRCUITS } from './data/presets';
import { fetchCompare, fetchTargets } from './lib/api';
import { decodePermalink, encodePermalink } from './lib/permalink';
import { registerOpenQasmLanguage } from './lib/qasmLanguage';
import { CompilerPane } from './components/CompilerPane';
import type { PaneConfig, TopologyProfile, TranspileResponse } from './types/compiler';

export default function App() {
  const initialHash = decodePermalink(window.location.hash);

  const [preset, setPreset] = useState('qft4');
  const [qasm, setQasm] = useState(initialHash?.qasm ?? PRESET_CIRCUITS.qft4.qasm);
  const [shots, setShots] = useState(initialHash?.shots ?? 10000);
  const [ibmTier, setIbmTier] = useState(initialHash?.ibmTier ?? 'payg');
  const [paneA, setPaneA] = useState<PaneConfig>(
    initialHash?.paneA ?? { target_id: 'ibm_heron_r3_patch', compiler: 'qiskit', opt_level: 2, layout_strategy: 'degree_aware' },
  );
  const [paneB, setPaneB] = useState<PaneConfig>(
    initialHash?.paneB ?? { target_id: 'ionq_forte_clique', compiler: 'builtin', opt_level: 2, layout_strategy: 'degree_aware' },
  );

  const [topologies, setTopologies] = useState<TopologyProfile[]>([]);
  const [resA, setResA] = useState<TranspileResponse | null>(null);
  const [resB, setResB] = useState<TranspileResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const [verifyEquiv, setVerifyEquiv] = useState(true);
  const [equivalence, setEquivalence] = useState<import('./types/compiler').EquivalenceResult | null>(null);

  useEffect(() => {
    fetchTargets().then(setTopologies).catch((e: Error) => setError(e.message));
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => {
      fetchCompare(qasm, shots, ibmTier, paneA, paneB, verifyEquiv, controller.signal)
        .then((data) => {
          setError(null);
          setResA(data.target_a);
          setResB(data.target_b);
          setEquivalence(data.equivalence ?? null);
        })
        .catch((e: Error) => {
          if (e.name !== 'AbortError') setError(e.message);
        });
    }, 250);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [qasm, shots, ibmTier, paneA, paneB, verifyEquiv]);

  function handleShare() {
    const hash = encodePermalink({ qasm, shots, ibmTier, paneA, paneB });
    window.history.replaceState(null, '', hash);
    navigator.clipboard?.writeText(window.location.href).catch(() => {});
    setToast('Permalink copied to clipboard');
    setTimeout(() => setToast(null), 2200);
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <header className="border-b border-slate-800 px-4 py-2.5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-cyan-500/15 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
            <Cpu className="w-4 h-4" />
          </div>
          <div>
            <h1 className="text-sm sm:text-base font-semibold tracking-tight">Quantum Compiler Explorer</h1>
            <p className="text-xs text-slate-400 hidden sm:block">Side-by-side OpenQASM 3 transpilation, SWAP heatmaps, and QPU cost estimator</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={preset}
            onChange={(e) => {
              setPreset(e.target.value);
              setQasm(PRESET_CIRCUITS[e.target.value].qasm);
            }}
            className="bg-slate-900 border border-slate-700 rounded-md px-2.5 py-1.5 text-xs text-slate-200"
          >
            {Object.entries(PRESET_CIRCUITS).map(([k, v]) => (
              <option key={k} value={k}>{v.label}</option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => setQasm(PRESET_CIRCUITS[preset].qasm)}
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-md bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Reset</span>
          </button>
          <button
            type="button"
            onClick={handleShare}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-cyan-600 hover:bg-cyan-500 text-white"
          >
            <Link2 className="w-3.5 h-3.5" />
            <span>Share Link</span>
          </button>
        </div>
      </header>

      <section className="border-b border-slate-800 bg-slate-900/60 px-4 py-2 flex flex-wrap items-center justify-between gap-4 text-xs">
        <div className="flex flex-wrap items-center gap-4">
          <label className="flex items-center gap-2 text-slate-400">
            <span>Shots:</span>
            <input type="range" min={100} max={50000} step={100} value={Math.min(50000, shots)} onChange={(e) => setShots(Number(e.target.value))} className="w-28 accent-cyan-500" />
            <input type="number" min={1} max={1000000} value={shots} onChange={(e) => setShots(Math.max(1, Number(e.target.value) || 1))} className="w-20 bg-slate-950 border border-slate-700 rounded px-2 py-1 font-mono text-slate-100" />
          </label>
          <label className="flex items-center gap-2 text-slate-400">
            <span>IBM Tier:</span>
            <select value={ibmTier} onChange={(e) => setIbmTier(e.target.value)} className="bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200">
              <option value="payg">Pay-As-You-Go ($96/min)</option>
              <option value="flex">Flex ($72/min)</option>
              <option value="premium">Premium ($48/min)</option>
              <option value="open">Open Plan (Free 10m/mo)</option>
            </select>
          </label>
          <label className="flex items-center gap-1.5 text-slate-400 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={verifyEquiv}
              onChange={(e) => setVerifyEquiv(e.target.checked)}
              className="rounded accent-cyan-500"
            />
            <span>Verify Equivalence</span>
          </label>
        </div>
        {resA && resB && (
          <div className="flex flex-wrap items-center gap-2 font-mono">
            {equivalence && (
              <span className={`px-2 py-1 rounded border text-[11px] ${equivalence.equivalent ? 'bg-emerald-950/70 border-emerald-700 text-emerald-300' : 'bg-rose-950/70 border-rose-700 text-rose-300'}`}>
                Equiv: {equivalence.equivalent ? '✓ Match (100%)' : `✗ Differs (${(equivalence.fidelity * 100).toFixed(0)}%)`}
              </span>
            )}
            <span className="px-2 py-1 rounded bg-slate-950 border border-slate-800">
              SWAP Delta: {resA.inserted_swaps - resB.inserted_swaps > 0 ? `+${resA.inserted_swaps - resB.inserted_swaps}` : resA.inserted_swaps - resB.inserted_swaps}
            </span>
            <span className="px-2 py-1 rounded bg-slate-950 border border-slate-800">
              Cost: ${resA.cost_estimate.estimated_cost_usd.toFixed(2)} vs ${resB.cost_estimate.estimated_cost_usd.toFixed(2)}
            </span>
          </div>
        )}
      </section>

      <main className="flex-1 p-3 sm:p-4 grid grid-cols-1 xl:grid-cols-12 gap-3 sm:gap-4">
        <section className="xl:col-span-4 flex flex-col rounded-xl border border-slate-800 bg-slate-900/70 overflow-hidden min-h-[540px]">
          <div className="px-3 py-2 border-b border-slate-800 bg-slate-900 flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-300">Logical Source (OpenQASM 3)</span>
            {resA && (
              <span className="text-[11px] font-mono text-slate-400">
                {resA.logical_metrics.two_qubit_gates} 2Q gates | depth {resA.logical_metrics.depth}
              </span>
            )}
          </div>
          {error && <div className="px-3 py-2 bg-rose-950/80 border-b border-rose-800 text-rose-200 text-xs font-mono">{error}</div>}
          <div className="flex-1 min-h-[460px]">
            <Editor
              height="100%"
              defaultLanguage="openqasm3"
              theme="vs-dark"
              value={qasm}
              onChange={(v) => setQasm(v ?? '')}
              beforeMount={registerOpenQasmLanguage}
              options={{ minimap: { enabled: false }, fontSize: 13, automaticLayout: true }}
            />
          </div>
        </section>

        <CompilerPane title="Target A" accentClass="text-cyan-400" config={paneA} topologies={topologies} result={resA} onChange={setPaneA} />
        <CompilerPane title="Target B" accentClass="text-amber-400" config={paneB} topologies={topologies} result={resB} onChange={setPaneB} />
      </main>

      {toast && (
        <div className="fixed bottom-4 right-4 px-3.5 py-2 rounded-lg bg-slate-800 border border-cyan-500/40 text-xs text-slate-100 shadow-lg">
          {toast}
        </div>
      )}
    </div>
  );
}
