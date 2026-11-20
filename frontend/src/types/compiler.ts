export interface TopologyNode {
  id: number;
  x: number;
  y: number;
}

export interface TopologyProfile {
  id: string;
  name: string;
  vendor: string;
  architecture: string;
  full_chip_qubits: number;
  patch_qubits: number;
  basis_gates: string[];
  two_qubit_gate: string;
  two_qubit_error_rate: number;
  single_qubit_error_rate: number;
  circuits_per_second: number;
  pricing_provider: string;
  nodes: TopologyNode[];
  edges: [number, number][];
}

export interface GateOpDto {
  name: string;
  qubits: number[];
  params: string[];
  source_line: number;
  is_swap: boolean;
}

export interface StageMetrics {
  total_gates: number;
  single_qubit_gates: number;
  two_qubit_gates: number;
  inserted_swaps: number;
  depth: number;
}

export interface StageSnapshot {
  stage: string;
  label: string;
  qasm: string;
  metrics: StageMetrics;
  ops: GateOpDto[];
}

export interface CostEstimate {
  provider: string;
  model: 'per_minute' | 'per_task_plus_shot';
  is_exact_formula: boolean;
  shots: number;
  estimated_seconds: number | null;
  estimated_cost_usd: number;
  formula: string;
}

export interface TranspileResponse {
  compiler: string;
  target_id: string;
  logical_metrics: StageMetrics;
  initial_layout: Record<string, number>;
  final_layout: Record<string, number>;
  edge_usage: Record<string, number>;
  swap_edges: Record<string, number>;
  inserted_swaps: number;
  stages: StageSnapshot[];
  final_metrics: StageMetrics;
  final_qasm: string;
  estimated_fidelity: number;
  cost_estimate: CostEstimate;
  cache_hit: boolean;
}

export interface PaneConfig {
  target_id: string;
  compiler: 'builtin' | 'qiskit' | 'pytket' | 'cirq';
  opt_level: number;
  layout_strategy: 'degree_aware' | 'trivial';
}

export interface EquivalenceResult {
  equivalent: boolean;
  num_qubits: number;
  fidelity: number;
  method: string;
  message: string;
}
