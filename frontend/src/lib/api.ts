import type { PaneConfig, TopologyProfile, TranspileResponse } from '../types/compiler';

export async function fetchTargets(): Promise<TopologyProfile[]> {
  const res = await fetch('/api/v1/targets');
  if (!res.ok) throw new Error('Failed to load target topologies');
  const data = await res.json();
  return data.targets as TopologyProfile[];
}

export async function fetchCompare(
  qasm: string,
  shots: number,
  ibmTier: string,
  targetA: PaneConfig,
  targetB: PaneConfig,
  verifyEquivalence: boolean = false,
  signal?: AbortSignal,
): Promise<{ target_a: TranspileResponse; target_b: TranspileResponse; equivalence?: import('../types/compiler').EquivalenceResult }> {
  const res = await fetch('/api/v1/compare', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      qasm,
      shots,
      ibm_tier: ibmTier,
      target_a: targetA,
      target_b: targetB,
      verify_equivalence: verifyEquivalence,
    }),
    signal,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Comparison failed' }));
    const msg = typeof err.detail === 'string' ? err.detail : err.detail?.message ?? 'Transpilation error';
    throw new Error(msg);
  }
  return res.json();
}
