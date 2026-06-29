import React from 'react';
import katex from 'katex';
import 'katex/dist/katex.min.css';

// Renders text that may contain inline LaTeX delimited by $...$ (and \( \)).
// On the current data (no LaTeX) it just renders plain text — zero regression.
// After MinerU re-extraction, math displays properly.

function renderTex(tex) {
  try {
    return katex.renderToString(tex, { throwOnError: false, output: 'html' });
  } catch {
    return tex;
  }
}

const INLINE = /\$([^$]+?)\$|\\\((.+?)\\\)/g;

export default function MathText({ children }) {
  const text = String(children ?? '');
  if (!text.includes('$') && !text.includes('\\(')) return <>{text}</>;

  const parts = [];
  let last = 0;
  let m;
  while ((m = INLINE.exec(text)) !== null) {
    if (m.index > last) parts.push({ t: 'text', v: text.slice(last, m.index) });
    parts.push({ t: 'math', v: m[1] ?? m[2] });
    last = INLINE.lastIndex;
  }
  if (last < text.length) parts.push({ t: 'text', v: text.slice(last) });

  return (
    <>
      {parts.map((p, i) =>
        p.t === 'math'
          ? <span key={i} dangerouslySetInnerHTML={{ __html: renderTex(p.v) }} />
          : <span key={i}>{p.v}</span>
      )}
    </>
  );
}
