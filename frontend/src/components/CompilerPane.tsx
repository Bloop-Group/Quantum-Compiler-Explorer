import { useState } from 'react';
import type { PaneConfig, TopologyProfile, TranspileResponse } from '../types/compiler';
import { CircuitSvg } from './CircuitSvg';
import { TopologyMapSvg } from './TopologyMapSvg';

interface Props {
  title: string;
  accentClass: string;
  config: PaneConfig;
  topologies: TopologyProfile[];
  result: TranspileResponse | null;
  onChange: (next: PaneConfig) => void;
}

export function CompilerPane({ title, accentClass, config, topologies, result, onChange }: Props) {
  const [stageIdx, setStageIdx] = useState(4);
  const [view, setView] = useState<'qasm' | 'circuit' | 'topology'>('qasm');

  const topology = topologies.find((t) => t.id === config.target_id);
  const stages = result?.stages ?? [];
  const safeIdx = Math.min(stageIdx, Math.max(0, stages.length - 1));
  const stage = stages[safeIdx];

  const twoQDelta = result ? result.final_metrics.two_qubit_gates - result.logical_metrics.two_qubit_gates : 0;
  const fidPct = result ? result.estimated_fidelity * 100 : 0;
  const fidColor = fidPct >= 85 ? 'text-emerald-400' : fidPct >= 50 ? 'text-amber-400' : 'text-rose-400';

  return (
    <section className="xl:col-span-4 flex flex-col rounded-xl border border-slate-800 bg-slate-900/70 overflow-hidden min-h-[540px]">
      <div className="px-3 py-2 border-b border-slate-800 bg-slate-900 flex flex-wrap items-center justify-between gap-2">
        <span className={`text-xs font-semibold uppercase tracking-wider ${accentClass}`}>{title}</span>
        <div className="flex flex-wrap items-center gap-1.5">
          <select
            value={config.compiler}
            onChange={(e) => onChange({ ...config, compiler: e.target.value as PaneConfig['compiler'] })}
            className="bg-slate-950 border border-slate-700 rounded px-1.5 py-1 text-[11px] text-slate-200"
          >
            <option value="builtin">Builtin</option>
            <option value="qiskit">Qiskit</option>
            <option value="pytket">pytket</option>
            <option value="cirq">Cirq</option>
          </select>
          <select
            value={config.target_id}
            onChange={(e) => onChange({ ...config, target_id: e.target.value })}
            className="bg-slate-950 border border-slate-700 rounded px-2 py-1 text-[11px] text-slate-200 max-w-[165px]"
          >
            {topologies.map((t) => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
          <select
            value={config.opt_level}
            onChange={(e) => onChange({ ...config, opt_level: Number(e.target.value) })}
            className="bg-slate-950 border border-slate-700 rounded px-1.5 py-1 text-[11px] font-mono text-slate-200"
          >
            {[0, 1, 2, 3].map((o) => <option key={o} value={o}>{`O${o}`}</option>)}
          </select>
          <select
            value={config.layout_strategy}
            onChange={(e) => onChange({ ...config, layout_strategy: e.target.value as PaneConfig['layout_strategy'] })}
            className="bg-slate-950 border border-slate-700 rounded px-1.5 py-1 text-[11px] text-slate-200"
          >
            <option value="degree_aware">Degree-Aware</option>
            <option value="trivial">Trivial</option>
          </select>
        </div>
      </div>

      {!result || !stage ? (
        <div className="p-4 text-xs text-slate-400">Waiting for transpilation output...</div>
      ) : (
        <div className="p-3 space-y-3 flex-1 flex flex-col">
          <div className="grid grid-cols-4 gap-2">
            <div className="rounded-lg bg-slate-950 border border-slate-800 p-2">
              <div className="text-[10px] uppercase tracking-wider text-slate-500">SWAPs</div>
              <div className={`text-base font-mono font-semibold ${result.inserted_swaps > 0 ? 'text-rose-400' : 'text-emerald-400'}`}>
                {result.inserted_swaps}
              </div>
            </div>
            <div className="rounded-lg bg-slate-950 border border-slate-800 p-2">
              <div className="text-[10px] uppercase tracking-wider text-slate-500">2Q Gates</div>
              <div className="text-base font-mono font-semibold text-slate-100">
                {result.final_metrics.two_qubit_gates}{' '}
                <span className={`text-[11px] ${twoQDelta > 0 ? 'text-rose-400' : 'text-emerald-400'}`}>
                  ({twoQDelta > 0 ? `+${twoQDelta}` : twoQDelta})
                </span>
              </div>
            </div>
            <div className="rounded-lg bg-slate-950 border border-slate-800 p-2">
              <div className="text-[10px] uppercase tracking-wider text-slate-500">Est. Fid.</div>
              <div className={`text-base font-mono font-semibold ${fidColor}`}>{fidPct.toFixed(1)}%</div>
            </div>
            <div className="rounded-lg bg-slate-950 border border-slate-800 p-2">
              <div className="text-[10px] uppercase tracking-wider text-slate-500">Est. Cost</div>
              <div className="text-base font-mono font-semibold text-slate-100">
                ${result.cost_estimate.estimated_cost_usd < 10
                  ? result.cost_estimate.estimated_cost_usd.toFixed(2)
                  : result.cost_estimate.estimated_cost_usd.toFixed(0)}
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap gap-1">
              {stages.map((s, idx) => (
                <button
                  key={`${s.stage}-${idx}`}
                  type="button"
                  onClick={() => setStageIdx(idx)}
                  className={`px-2 py-1 text-[11px] font-medium rounded transition ${
                    idx === safeIdx
                      ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
                      : 'bg-slate-950/70 text-slate-400 border border-slate-800 hover:text-slate-200'
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-1 bg-slate-950 p-0.5 rounded-lg border border-slate-800">
              {(['qasm', 'circuit', 'topology'] as const).map((k) => (
                <button
                  key={k}
                  type="button"
                  onClick={() => setView(k)}
                  className={`px-2.5 py-1 text-[11px] font-medium rounded-md transition ${
                    view === k ? 'bg-slate-800 text-slate-100 border border-slate-600' : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {k === 'qasm' ? 'QASM Diff' : k === 'circuit' ? 'Circuit SVG' : 'Chip Map'}
                </button>
              ))}
            </div>
          </div>

          <div className="flex-1">
            {view === 'qasm' && (
              <div className="bg-slate-950 rounded-lg border border-slate-800 py-2 max-h-[340px] overflow-auto font-mono text-xs">
                {stage.qasm.split('\n').map((line, i) => (
                  <div key={i} className={`flex px-2 leading-5 ${line.includes('[SWAP]') || line.startsWith('swap ') ? 'line-swap' : 'line-native'}`}>
                    <span className="w-7 shrink-0 text-right pr-2 text-slate-600 select-none">{i + 1}</span>
                    <span className="whitespace-pre text-slate-200">{line}</span>
                  </div>
                ))}
              </div>
            )}
            {view === 'circuit' && <CircuitSvg ops={stage.ops} numQubits={topology?.patch_qubits ?? 12} />}
            {view === 'topology' && topology && <TopologyMapSvg topology={topology} result={result} />}
          </div>

          <div className="text-[11px] text-slate-400 bg-slate-950/70 border border-slate-800/80 rounded-md px-2.5 py-1.5 flex items-center justify-between gap-2">
            <span className="truncate">{result.cost_estimate.formula}</span>
            <span className="shrink-0 font-mono text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">
              {result.cache_hit ? 'Cache Hit' : result.cost_estimate.is_exact_formula ? 'Exact Rate' : 'Time Est.'}
            </span>
          </div>
        </div>
      )}
    </section>
  );
}
