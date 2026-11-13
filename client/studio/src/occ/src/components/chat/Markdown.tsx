// Video Tool: changed from OpenChatCut src/components/chat/Markdown.tsx @ 9242a95 (AGPL-3.0-or-later, see src/occ/NOTICE.md). Upstream
// renders with react-markdown + remark-gfm; Video Tool's director answers in short plain sentences, so this renders the small part of
// Markdown it uses (paragraphs, "-" / "*" / "1." lists, **bold**, `code`, http links) as React elements: no HTML from the text is ever
// injected, which keeps the same safety as upstream. Same props, same `.cc-md` class.
import type { CSSProperties, ReactNode } from 'react';
import { theme } from '../../theme';

interface MarkdownProps {
  text: string;
  style?: CSSProperties;
}

function inline(text: string, key: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`|https?:\/\/[^\s)]+)/g;
  let at = 0, m: RegExpExecArray | null, n = 0;
  while ((m = re.exec(text))) {
    if (m.index > at) out.push(text.slice(at, m.index));
    const t = m[0];
    if (t.startsWith('**')) out.push(<strong key={`${key}b${n++}`}>{t.slice(2, -2)}</strong>);
    else if (t.startsWith('`')) out.push(<code key={`${key}c${n++}`}>{t.slice(1, -1)}</code>);
    else out.push(<a key={`${key}a${n++}`} href={t} target="_blank" rel="noreferrer">{t}</a>);
    at = m.index + t.length;
  }
  if (at < text.length) out.push(text.slice(at));
  return out;
}

export function Markdown({ text, style }: MarkdownProps) {
  if (!text) return null;
  const blocks: ReactNode[] = [];
  const lines = text.replace(/\r/g, '').split('\n');
  for (let i = 0; i < lines.length;) {
    if (!lines[i].trim()) { i++; continue; }
    const bullet = /^\s*([-*]|\d+\.)\s+/;
    if (bullet.test(lines[i])) {
      const ordered = /^\s*\d+\./.test(lines[i]);
      const items: ReactNode[] = [];
      while (i < lines.length && bullet.test(lines[i])) { items.push(<li key={i}>{inline(lines[i].replace(bullet, ''), `l${i}`)}</li>); i++; }
      blocks.push(ordered ? <ol key={`o${i}`}>{items}</ol> : <ul key={`u${i}`}>{items}</ul>);
      continue;
    }
    const para: string[] = [];
    while (i < lines.length && lines[i].trim() && !bullet.test(lines[i])) para.push(lines[i++]);
    blocks.push(<p key={`p${i}`}>{inline(para.join(' '), `p${i}`)}</p>);
  }
  return <div className="cc-md" style={{ color: theme.text, wordBreak: 'break-word', lineHeight: 1.6, ...style }}>{blocks}</div>;
}
