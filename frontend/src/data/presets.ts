export const PRESET_CIRCUITS: Record<string, { label: string; qasm: string }> = {
  qft4: {
    label: 'Preset: 4-Qubit QFT',
    qasm: `OPENQASM 3.0;
include "stdgates.inc";
qubit[4] q;
bit[4] c;
// 4-Qubit QFT core entangling pattern
h q[0];
cx q[1], q[0];
rz(pi/4) q[0];
cx q[2], q[0];
rz(pi/8) q[0];
cx q[3], q[0];
h q[1];
cx q[2], q[1];
rz(pi/4) q[1];
cx q[3], q[1];
h q[2];
cx q[3], q[2];
h q[3];
c[0] = measure q[0];
c[1] = measure q[1];
c[2] = measure q[2];
c[3] = measure q[3];`,
  },
  ghz3: {
    label: 'Preset: 3-Qubit GHZ State',
    qasm: `OPENQASM 3.0;
include "stdgates.inc";
qubit[3] q;
bit[3] c;
h q[0];
cx q[0], q[1];
cx q[0], q[2];
barrier q;
c[0] = measure q[0];
c[1] = measure q[1];
c[2] = measure q[2];`,
  },
  star5: {
    label: 'Preset: 5-Qubit Star Entangler',
    qasm: `OPENQASM 3.0;
include "stdgates.inc";
qubit[5] q;
bit[5] c;
h q[0];
cx q[0], q[1];
cx q[0], q[2];
cx q[0], q[3];
cx q[0], q[4];
rz(pi/2) q[0];
cx q[4], q[1];
cx q[3], q[2];
c[0] = measure q[0];`,
  },
  grover3: {
    label: 'Preset: 3-Qubit Grover (CCX)',
    qasm: `OPENQASM 3.0;
include "stdgates.inc";
qubit[3] q;
bit[3] c;
h q[0];
h q[1];
h q[2];
ccx q[0], q[1], q[2];
barrier q;
h q[0];
h q[1];
x q[0];
x q[1];
cz q[0], q[1];
x q[0];
x q[1];
h q[0];
h q[1];
c[0] = measure q[0];`,
  },
  qaoa6: {
    label: 'Preset: 6-Qubit QAOA MaxCut',
    qasm: `OPENQASM 3.0;
include "stdgates.inc";
qubit[6] q;
bit[6] c;
h q[0]; h q[1]; h q[2]; h q[3]; h q[4]; h q[5];
cx q[0], q[1]; rz(0.4) q[1]; cx q[0], q[1];
cx q[1], q[2]; rz(0.4) q[2]; cx q[1], q[2];
cx q[2], q[3]; rz(0.4) q[3]; cx q[2], q[3];
cx q[3], q[4]; rz(0.4) q[4]; cx q[3], q[4];
cx q[4], q[5]; rz(0.4) q[5]; cx q[4], q[5];
cx q[5], q[0]; rz(0.4) q[0]; cx q[5], q[0];
cx q[0], q[3]; rz(0.4) q[3]; cx q[0], q[3];
rx(0.7) q[0]; rx(0.7) q[1]; rx(0.7) q[2];
rx(0.7) q[3]; rx(0.7) q[4]; rx(0.7) q[5];`,
  },
};
