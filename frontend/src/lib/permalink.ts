import LZString from 'lz-string';
import type { PaneConfig } from '../types/compiler';

export interface SharePayload {
  qasm: string;
  shots: number;
  ibmTier: string;
  paneA: PaneConfig;
  paneB: PaneConfig;
}

export function encodePermalink(payload: SharePayload): string {
  const compressed = LZString.compressToEncodedURIComponent(JSON.stringify(payload));
  return `#s=${compressed}`;
}

export function decodePermalink(hash: string): Partial<SharePayload> | null {
  if (!hash.startsWith('#s=')) return null;
  try {
    const raw = LZString.decompressFromEncodedURIComponent(hash.slice(3));
    if (!raw) return null;
    return JSON.parse(raw) as Partial<SharePayload>;
  } catch {
    return null;
  }
}
