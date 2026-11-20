# Closing the Developer Experience Gap in Quantum Compilation: A Thesis for a Quantum Compiler Explorer

**Author:** Sean Loper  
**Date:** November 20, 2026  

## Abstract

Quantum computing software has matured rapidly at the compiler and SDK layer, with mature Python and C++ toolchains such as Qiskit, Cirq, PennyLane, [pytket](https://docs.quantinuum.com/tket/user-guide/manual/manual_compiler.html), and [qBraid](https://github.com/qbraid/qbraid) handling circuit construction, transpilation, and cloud job submission. Yet the interactive developer-tools layer on top of those compilers remains stuck in static Jupyter plots and command-line logs. In classical systems programming, Matt Godbolt's [Compiler Explorer](https://xania.org/202506/how-compiler-explorer-works) transformed how engineers reason about optimization passes, instruction selection, and hardware trade-offs by making compilation immediate, visual, and shareable. Quantum computing has an even stronger need for that exact workflow: every extra two-qubit SWAP gate introduced during qubit routing directly degrades circuit fidelity and wastes real cloud budget. This thesis argues that building an open-source, browser-first **Quantum Compiler Explorer** is one of the highest-leverage gaps a full-stack software engineer can solve today without owning quantum hardware or inventing new physics.

## 1. The Observation: Great Compilers, Blind Developers

Looking at the quantum computing ecosystem from the perspective of a full-stack software engineer, the bottleneck is not a lack of backend math. Between [IBM's Qiskit](https://quantum.cloud.ibm.com/docs/api/qiskit/transpiler), Google's Cirq, Xanadu's PennyLane, Quantinuum's [pytket](https://github.com/CQCL/pytket-qiskit), the [Munich Quantum Toolkit](https://github.com/openqasm/openqasm/blob/main/implementations.md), and cross-platform runtimes like [qBraid](https://github.com/qbraid/qbraid), the industry already has serious, well-funded compilation libraries.

What is missing is visibility. When a developer writes a logical quantum circuit and targets a physical quantum processing unit (QPU), the transpiler performs a series of aggressive rewrites: mapping logical qubits onto physical hardware wires, inserting SWAP gates whenever two interacting qubits are not physically adjacent, decomposing high-level gates into the chip's native basis set, and cancelling redundant rotations ([How Quantum Programs Are Compiled](https://safeguard.sh/resources/blog/how-quantum-programs-are-compiled-openqasm-3-transpilation-qubit-routing-and-open-source-sdks)).

In classical computing, a bad compiler pass might cost you a few nanoseconds of CPU time. On noisy quantum hardware in 2026, a bad layout or routing choice can destroy the entire computation. Even a small 3-qubit GHZ circuit that requires 2 two-qubit gates on an optimal physical layout can expand to 5 two-qubit gates on a poor layout ([Safeguard.sh](https://safeguard.sh/resources/blog/how-quantum-programs-are-compiled-openqasm-3-transpilation-qubit-routing-and-open-source-sdks)). Meanwhile, the hardware landscape itself is diverging: IBM's [Heron r2 and r3](https://quantum.cloud.ibm.com/docs/en/guides/processor-types) processors use a 156-qubit heavy-hexagonal lattice, IBM's newer [Nighthawk r2](https://nand-research.com/ibm-quantum-nighthawk-r2-arrives-on-the-ibm-quantum-platform/) uses a four-degree square lattice specifically to cut compilation overhead, and trapped-ion systems like [IonQ Forte](https://docs.ionq.com/features/getting-started-with-native-gates) offer all-to-all connectivity with different native gates and pricing structures.

Today, comparing how a circuit compiles across those topologies means writing boilerplate Python scripts, exporting static images in notebooks, and manually cross-referencing pricing pages. There is no fast, zero-setup web workbench where you can paste an [OpenQASM 3](https://quantum.cloud.ibm.com/docs/guides/introduction-to-qasm) circuit, switch target chips and compilers side by side, and immediately see where SWAP gates explode.

## 2. Why This Gap Matters Financially and Practically

Blind transpilation is not just an academic annoyance; it carries a direct financial cost. Cloud QPU access in late 2026 uses radically different billing models across providers ([Quantum Computing Cost 2026](https://quantumcomputingcost.com/)):

* **IBM Quantum** bills by QPU runtime: Pay-As-You-Go runs $96 per minute, with committed tiers at $72 per minute (Flex) and $48 per minute (Premium) ([Quantum Computing Cost 2026](https://quantumcomputingcost.com/)).
* **AWS Braket** charges $0.30 per task plus a device-specific per-shot rate ranging from $0.000425 per shot on Rigetti Cepheus and $0.00145 on IQM Garnet up to $0.08000 per shot on IonQ Forte, putting a 10,000-shot job at roughly $800.30 on IonQ Forte ([AWS Braket Pricing](https://aws.amazon.com/braket/pricing/), [Quantum Computing Cost 2026](https://quantumcomputingcost.com/)).
* **Azure Quantum** mixes time-based billing (such as $120 per minute on Rigetti Cepheus) with high-tier monthly hardware subscriptions ([Quantum Computing Cost Calculator](https://quantumcomputingcost.com/calculator/), [Azure Quantum Pricing](https://learn.microsoft.com/en-us/azure/quantum/pricing)).

Submitting a circuit whose transpiled depth pushes expected two-qubit fidelity near random noise is equivalent to burning cloud credits for static. A pre-flight compiler explorer that pairs topological SWAP inspection with transparent noise-decay estimates and provider cost math solves an immediate, real-world problem before a single paid job is queued.

## 3. Survey of Existing Open-Source Tools

A direct audit of GitHub and the open-source quantum ecosystem confirms that the gap is specifically at the interactive compiler-inspection layer:

1. **Cross-SDK backends exist:** [qBraid/qBraid](https://github.com/qbraid/qbraid) and [pytket](https://github.com/CQCL/pytket-qiskit) already solve programmatic circuit translation and optimization across frameworks. Rebuilding another Python transpiler from scratch would duplicate years of specialized compiler research.
2. **Educational simulators exist:** Tools like [Strilanc/Quirk](https://github.com/strilanc/quirk) and [microsoft/quantum-viz.js](https://github.com/microsoft/quantum-viz.js/) are great for learning ideal logical gates in a browser, but they do not model hardware coupling maps, SWAP routing, native basis translation, or cloud cost.
3. **Interactive compiler explorers barely exist:** Searches turn up small student prototypes such as [JakuJ/quantum-explorer](https://github.com/JakuJ/quantum-explorer) (a Q# thesis project) and academic prototypes like [UST-QuAntiL/QuantumTranspiler](https://github.com/UST-QuAntiL/QuantumTranspiler), rather than a maintained, multi-compiler, Godbolt-grade web application.
4. **Compiler reliability still needs visibility:** Recent cross-platform testing research ([IterTestQ, ISSTA 2026](https://software-lab.org/publications/issta2026_IterTestQ.pdf)) uncovered 23 bugs across Qiskit, PennyLane, pytket, BQSKit, and Cirq. Making side-by-side compiler outputs inspectable and shareable via URL helps the entire community spot regressions and compare optimization passes.

## 4. The Core Thesis: Wrap the Physics, Build the DevTools

My thesis is straightforward: **the highest-value contribution a full-stack engineer can make to quantum computing right now is building the interactive developer-tools layer that wraps existing open-source quantum compilers.**

Specifically, a Quantum Compiler Explorer should follow four design principles borrowed from [Compiler Explorer](https://xania.org/202506/how-compiler-explorer-works) and adapted to quantum hardware realities:

1. **OpenQASM 3 as the safe, universal input:** Accepting declarative [OpenQASM 3](https://quantum.cloud.ibm.com/docs/guides/introduction-to-qasm) first eliminates the arbitrary-code-execution risk of raw Python scripts while staying vendor-neutral across Qiskit, Cirq, pytket, and qBraid. Sandboxed Python input can be layered in later using strict process isolation (`nsjail` or ephemeral `--network=none` containers).
2. **Pass-by-pass transparency over fake line mapping:** Because quantum optimizers fuse and cancel gates at higher optimization levels, exact 1-to-1 source-line highlighting breaks down at `-O2` and `-O3`. Instead, hooking into Qiskit's [PassManager callbacks](https://quantum.cloud.ibm.com/docs/api/qiskit/qiskit.transpiler.PassManager) and pytket's [CompilationUnit callbacks](https://docs.quantinuum.com/tket/api-docs/passes.html) lets users scrub through every stage (Init, Layout, Routing, Basis Translation, Optimization) and see exactly where gate count and depth change.
3. **Hardware-first visualization:** Textual assembly diffs are not enough for quantum circuits. Every compiled output should pair its transpiled OpenQASM diff with an interactive coupling-map graph that highlights active physical qubits, hot SWAP edges, and cumulative two-qubit error estimates.
4. **Zero-setup defaults with shareable permalinks:** Shipping public reference hardware profiles and pricing formulas lets anyone open the app, paste a circuit, compare IBM heavy-hex vs. square-lattice vs. trapped-ion routing, and share a compressed URL link without needing vendor API keys. Optional Bring Your Own Key (BYOK) support can later pull live daily calibration data.

## 5. Conclusion

Quantum hardware teams are racing to build better qubits and lower error rates, and compiler researchers are building better routing heuristics. Between them sits a wide-open software engineering gap: a fast, visual, side-by-side workbench that turns quantum compilation from an opaque notebook print statement into an interactive engineering feedback loop. Because the underlying compilers, OpenQASM 3 parsers, coupling-map specs, and pricing formulas are already public, this is a tool that can be architected, prototyped, and shipped to the open-source community today.
