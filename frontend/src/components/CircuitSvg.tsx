import type { GateOpDto } from '../types/compiler';

interface Props {
  ops: GateOpDto[];
  numQubits: number;
}

export function CircuitSvg({ ops, numQubits }: Props) {
  const active = new Set<number>();
  ops.forEach((o) => o.qubits.forEach((q) => active.add(q)));
  const qList = active.size > 0
    ? Array.from(active).sort((a, b) => a - b)
    : Array.from({ length: Math.min(numQubits, 6) }, (_, i) => i);

  const qRow: Record<number, number> = {};
  qList.forEach((q, idx) => { qRow[q] = idx; });

  const visibleOps = ops.filter((o) => o.name !== 'barrier').slice(0, 34);
  const wireNextCol = new Array(qList.length).fill(0);
  const placed: Array<{ op: GateOpDto; col: number; rows: number[] }> = [];

  for (const op of visibleOps) {
    const rows = op.qubits.map((q) => qRow[q]).filter((r) => r !== undefined);
    if (!rows.length) continue;
    const minR = Math.min(...rows);
    const maxR = Math.max(...rows);
    let col = 0;
    for (let r = minR; r <= maxR; r++) col = Math.max(col, wireNextCol[r]);
    for (let r = minR; r <= maxR; r++) wireNextCol[r] = col + 1;
    placed.push({ op, col, rows });
  }

  const maxCols = Math.max(4, ...wireNextCol);
  const colW = 44;
  const rowH = 34;
  const padL = 48;
  const padT = 22;
  const width = Math.max(360, padL + maxCols * colW + 24);
  const height = padT + qList.length * rowH + 18;

  return (
    <div className="overflow-x-auto bg-slate-950 rounded-lg border border-slate-800 p-2">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto min-w-[340px]">
        {qList.map((q, idx) => {
          const y = padT + idx * rowH + 12;
          return (
            <g key={q}>
              <text x="8" y={y + 4} fill="#94a3b8" fontSize="11" fontFamily="monospace">
                {`q[${q}]`}
              </text>
              <line x1={padL - 4} y1={y} x2={width - 12} y2={y} stroke="#334155" strokeWidth="1.5" />
            </g>
          );
        })}

        {placed.map(({ op, col, rows }, idx) => {
          const x = padL + col * colW + 18;
          if (op.name === 'swap' && rows.length === 2) {
            const y1 = padT + rows[0] * rowH + 12;
            const y2 = padT + rows[1] * rowH + 12;
            return (
              <g key={idx}>
                <line x1={x} y1={y1} x2={x} y2={y2} stroke="#f43f5e" strokeWidth="2" />
                {[y1, y2].map((y) => (
                  <g key={y}>
                    <line x1={x - 6} y1={y - 6} x2={x + 6} y2={y + 6} stroke="#fb7185" strokeWidth="2" />
                    <line x1={x + 6} y1={y - 6} x2={x - 6} y2={y + 6} stroke="#fb7185" strokeWidth="2" />
                  </g>
                ))}
              </g>
            );
          }
          if (rows.length === 2) {
            const y1 = padT + rows[0] * rowH + 12;
            const y2 = padT + rows[1] * rowH + 12;
            const stroke = op.is_swap ? '#f43f5e' : '#38bdf8';
            const fill = op.is_swap ? '#4c0519' : '#0c4a6e';
            return (
              <g key={idx}>
                <line x1={x} y1={y1} x2={x} y2={y2} stroke={stroke} strokeWidth="2" />
                <circle cx={x} cy={y1} r="4.5" fill={stroke} />
                <rect x={x - 13} y={y2 - 11} width="26" height="22" rx="4" fill={fill} stroke={stroke} strokeWidth="1.4" />
                <text x={x} y={y2 + 4} textAnchor="middle" fill="#f8fafc" fontSize="9.5" fontFamily="monospace">
                  {op.name.toUpperCase()}
                </text>
              </g>
            );
          }
          const y = padT + rows[0] * rowH + 12;
          const isMeas = op.name === 'measure';
          const fill = isMeas ? '#1e293b' : op.is_swap ? '#4c0519' : '#1e1b4b';
          const stroke = isMeas ? '#64748b' : op.is_swap ? '#fb7185' : '#818cf8';
          return (
            <g key={idx}>
              <rect x={x - 15} y={y - 11} width="30" height="22" rx="4" fill={fill} stroke={stroke} strokeWidth="1.3" />
              <text x={x} y={y + 4} textAnchor="middle" fill="#e2e8f0" fontSize="9" fontFamily="monospace">
                {isMeas ? 'M' : op.name.slice(0, 4).toUpperCase()}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
