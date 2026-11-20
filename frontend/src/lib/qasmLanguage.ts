import type * as Monaco from 'monaco-editor';

export function registerOpenQasmLanguage(monaco: typeof Monaco): void {
  if (monaco.languages.getLanguages().some((l) => l.id === 'openqasm3')) {
    return;
  }
  monaco.languages.register({ id: 'openqasm3' });
  monaco.languages.setMonarchTokensProvider('openqasm3', {
    keywords: ['OPENQASM', 'include', 'qubit', 'bit', 'qreg', 'creg', 'measure', 'barrier', 'reset', 'gate', 'if', 'for'],
    gates: ['h', 'x', 'y', 'z', 's', 'sdg', 't', 'tdg', 'sx', 'rx', 'ry', 'rz', 'cx', 'cz', 'swap', 'ccx', 'rzz', 'gpi', 'gpi2', 'ms'],
    tokenizer: {
      root: [
        [/\/\/.*$/, 'comment'],
        [/"[^"]*"/, 'string'],
        [/\b\d+(?:\.\d+)?\b/, 'number'],
        [/[a-zA-Z_]\w*/, {
          cases: {
            '@keywords': 'keyword',
            '@gates': 'type.identifier',
            '@default': 'identifier',
          },
        }],
      ],
    },
  });
}
