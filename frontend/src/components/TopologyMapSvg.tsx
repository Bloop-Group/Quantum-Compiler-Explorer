import type { TopologyProfile, TranspileResponse } from '../types/compiler';

interface Props {
  topology: TopologyProfile;
  result: TranspileResponse;
}

export function TopologyMapSvg({ topology, result }: Props) {
  const p2l: Record<number, string> = {};
  Object.entries(result.initial_layout).forEach(([l, p]) => { p2l[p] = l; });
  const nodeById = Object.fromEntries(topology.nodes.map((n) => [n.id, n]));

  return (
    <div className="bg-slate-950 rounded-lg border border-slate-800 p-2">
      <svg viewBox="0 0 390 330" className="w-full h-auto max-h-[300px]">
        {topology.edges.map(([u, v], idx) => {
          const a = nodeById[u];
          const b = nodeById[v];
          if (!a || !b) return null;
          const ek = `${Math.min(u, v)}-${Math.max(u, v)}`;
          const swaps = result.swap_edges[ek] ?? 0;
          const uses = result.edge_usage[ek] ?? 0;
          let stroke = '#1e293b';
          let width = topology.id === 'ionq_forte_clique' ? 0.8 : 1.6;
          let opacity = topology.id === 'ionq_forte_clique' ? 0.45 : 0.9;
          if (swaps > 0) {
            stroke = '#f43f5e';
            width = Math.min(5, 2.2 + swaps * 0.8);
            opacity = 1;
          } else if (uses > 0) {
            stroke = '#38bdf8';
            width = Math.min(4, 1.8 + uses * 0.4);
            opacity = 0.95;
          }
          return (
            <line key={idx} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={stroke} strokeWidth={width} strokeOpacity={opacity}>
              <title>{`Edge P${u}-P${v}: ${uses} 2Q ops, ${swaps} SWAPs`}</title>
            </line>
          );
        })}

        {topology.nodes.map((n) => {
          const lq = p2l[n.id];
          const active = lq !== undefined;
          return (
            <g key={n.id}>
              <circle
                cx={n.x}
                cy={n.y}
                r={active ? 16 : 12}
                fill={active ? '#0e7490' : '#0f172a'}
                stroke={active ? '#22d3ee' : '#334155'}
                strokeWidth={active ? 2 : 1.3}
              >
                <title>{`Physical P${n.id}${active ? ` (mapped from q[${lq}])` : ' (unused)'}`}</title>
              </circle>
              <text
                x={n.x}
                y={n.y + (active ? -1 : 4)}
                textAnchor="middle"
                fill={active ? '#f8fafc' : '#64748b'}
                fontSize={active ? 9.5 : 9}
                fontWeight="600"
                fontFamily="monospace"
              >
                {`P${n.id}`}
              </text>
              {active && (
                <text x={n.x} y={n.y + 10} textAnchor="middle" fill="#a5f3fc" fontSize="8.5" fontFamily="monospace">
                  {`q${lq}`}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      <div className="mt-2 pt-2 border-t border-slate-800/80 flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-400 px-1">
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-cyan-500 inline-block" />Mapped</span>
          <span className="inline-flex items-center gap-1"><span className="w-3 h-0.5 bg-sky-400 inline-block" />2Q Gate</span>
          <span className="inline-flex items-center gap-1"><span className="w-3 h-0.5 bg-rose-500 inline-block" />SWAP Heat</span>
        </div>
        <span className="font-mono text-slate-500">{topology.architecture}</span>
      </div>
    </div>
  );
}
