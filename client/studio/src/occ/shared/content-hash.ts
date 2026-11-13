// Ported from OpenChatCut (AGPL-3.0-or-later, github.com/0xsline/OpenChatCut) shared/content-hash.ts @ 9242a95. See src/occ/NOTICE.md.
const SHA256_HEX = /^[0-9a-fA-F]{64}$/;

/** Accept only a complete SHA-256 hex digest and persist its canonical lowercase form. */
export function normalizeSha256Hash(value: unknown): string | undefined {
  return typeof value === 'string' && SHA256_HEX.test(value)
    ? value.toLowerCase()
    : undefined;
}
