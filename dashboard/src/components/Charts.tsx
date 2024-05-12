"use client";

import { useEffect, useRef, useState, type CSSProperties, type PointerEvent } from "react";
import { scaleLinear } from "d3-scale";
import { profile, tickCount, type LedgerRow, type Step } from "@/lib/derive";
import { int, rho } from "@/lib/format";
import { useWidth } from "./chart";

// ------------------------------------------------------------------------------------------ the rep ruler

/**
 * One tick is one rep, whole ticks only, in rows of equal length so two rulers on one page share a scale. When the
 * count grows after the first paint (the visitor changed an assumption) the added ticks land one after another, the
 * last 200 only; under reduced motion they simply appear.
 */
export function RepRuler({ reps, perRow, label, animate = false }: { reps: number; perRow?: number; label: string; animate?: boolean }) {
  const [wrap, width] = useWidth<HTMLDivElement>(1100);
  const n = tickCount(reps);
  const per = perRow ?? (width < 640 ? 110 : 328);
  const pitch = width / per;
  const rows = Math.max(1, Math.ceil(n / per));
  const tall = width < 640 ? 16 : 22;
  const rowH = tall + 24;
  const prev = useRef(n);
  const [from, setFrom] = useState(n);
  useEffect(() => {
    if (!animate) return;
    setFrom(prev.current);
    prev.current = n;
  }, [n, animate]);
  const first = animate && n > from ? Math.max(from, n - 200) : n;
  const ticks = [];
  for (let i = 0; i < n; i++) {
    const row = Math.floor(i / per);
    const x = (i % per) * pitch + pitch / 2;
    const hundred = (i + 1) % 100 === 0;
    const y0 = row * rowH + 18 + (hundred ? 0 : 6);
    const isNew = animate && i >= first && n > from;
    ticks.push(
      <line
        key={i}
        className={`tk${isNew ? " new" : ""}`}
        x1={x}
        x2={x}
        y1={y0 + tall + (hundred ? 0 : -6)}
        y2={y0}
        strokeWidth={hundred ? 2.6 : 2}
        style={isNew ? ({ "--d": `${Math.min(480, (i - first) * 1.2)}ms` } as CSSProperties) : undefined}
      />,
    );
    if (hundred)
      ticks.push(
        <text key={`l${i}`} className="t-mute" x={x} y={row * rowH + 12} textAnchor="middle">
          {i + 1}
        </text>,
      );
  }
  return (
    <div ref={wrap}>
      <svg className="svg" viewBox={`0 0 ${width} ${rows * rowH + 6}`} width={width} height={rows * rowH + 6} role="img" aria-label={label}>
        {ticks}
      </svg>
    </div>
  );
}

// ------------------------------------------------------------------------------------------ the state ledger

export function StateLedger({ rows, label }: { rows: LedgerRow[]; label: string }) {
  const [wrap, width] = useWidth<HTMLDivElement>(700);
  const narrow = width < 520;
  const labelW = narrow ? 92 : 132;
  const figW = 56;
  const max = Math.max(...rows.map((r) => r.whole + 1));
  const pitch = Math.min(3, (width - labelW - figW - 8) / max);
  const rowH = 24;
  const h = rows.length * rowH + 4;
  return (
    <div ref={wrap}>
      <svg className="svg" viewBox={`0 0 ${width} ${h}`} width={width} height={h} role="img" aria-label={label}>
        {rows.map((r, i) => {
          const y = i * rowH;
          const x0 = labelW;
          return (
            <g key={r.state}>
              <text className="t-strong" x={0} y={y + 16}>
                {narrow ? r.state : r.name}
              </text>
              {Array.from({ length: r.whole }, (_, k) => (
                <line key={k} className="tk" x1={x0 + k * pitch} x2={x0 + k * pitch} y1={y + 20} y2={y + 4} strokeWidth={Math.min(2, pitch * 0.66)} />
              ))}
              {r.fraction > 0.02 && (
                <line className="tk" x1={x0 + r.whole * pitch} x2={x0 + r.whole * pitch} y1={y + 20} y2={y + 20 - 16 * r.fraction} strokeWidth={Math.min(2, pitch * 0.66)} />
              )}
              <text className="t-strong" x={x0 + (r.whole + 1) * pitch + 8} y={y + 16}>
                {r.reps.toFixed(1)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// ------------------------------------------------------------------------------------------ the ranked weight profile

export function ProfileChart({
  weights,
  ids,
  tone,
  title,
  facts,
}: {
  weights: number[];
  ids?: string[];
  tone: "ink" | "ink3";
  title: string;
  facts: string;
}) {
  const [wrap, width] = useWidth<HTMLDivElement>(520);
  const [rank, setRank] = useState<number | null>(null);
  const p = profile(weights);
  const m = { top: 22, right: 8, bottom: 22, left: 34 };
  const h = 250;
  const iw = width - m.left - m.right;
  const ih = h - m.top - m.bottom;
  const y = scaleLinear().domain([0, 2]).range([ih, 0]);
  const n = p.sorted.length;
  const x = (i: number) => (n > 1 ? (i / (n - 1)) * iw : 0);
  const idByWeight = ids ? [...ids.map((id, i) => ({ id, w: weights[i] }))].sort((a, b) => a.w - b.w) : null;
  const onMove = (e: PointerEvent<SVGRectElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    setRank(Math.min(n - 1, Math.max(0, Math.round(((e.clientX - r.left) / r.width) * (n - 1)))));
  };
  return (
    <div ref={wrap}>
      <p className="stat-line" style={{ margin: "0 0 6px", minHeight: 46 }}>
        <b>{title}</b> {facts}
      </p>
      <svg className="svg" viewBox={`0 0 ${width} ${h}`} width={width} height={h} role="img" aria-label={`${title} ${facts}`}>
        <g transform={`translate(${m.left},${m.top})`}>
          <rect className="tol" x={0} y={y(1.25)} width={iw} height={y(0.75) - y(1.25)} />
          <line className="tol-edge" x1={0} x2={iw} y1={y(1.25)} y2={y(1.25)} />
          <line className="tol-edge" x1={0} x2={iw} y1={y(0.75)} y2={y(0.75)} />
          {[0, 0.5, 1.5, 2].map((t) => (
            <g key={t}>
              <line className="grid" x1={0} x2={iw} y1={y(t)} y2={y(t)} />
              <text className="t-mute" x={-6} y={y(t) + 4} textAnchor="end">
                {t.toFixed(1)}
              </text>
            </g>
          ))}
          <line className="target" x1={0} x2={iw} y1={y(1)} y2={y(1)} />
          <text className="t-strong" x={-6} y={y(1) + 4} textAnchor="end">
            1.00
          </text>
          {p.sorted.map((w, i) => (
            <line key={i} className={tone === "ink" ? "prof" : "prof-3"} x1={x(i)} x2={x(i)} y1={ih} y2={y(Math.min(w, 2))} />
          ))}
          <text className="t-mute" x={4} y={y(1.25) - 5}>
            within 25% of the target
          </text>
          {rank != null && <line className="base" x1={x(rank)} x2={x(rank)} y1={0} y2={ih} />}
          <text className="t-mute" x={0} y={ih + 16}>
            lightest
          </text>
          <text className="t-mute" x={iw} y={ih + 16} textAnchor="end">
            heaviest
          </text>
          <rect x={0} y={0} width={iw} height={ih} fill="transparent" onPointerMove={onMove} onPointerLeave={() => setRank(null)} />
        </g>
      </svg>
      <p className="readout" aria-live="polite" style={{ minHeight: 22 }}>
        {rank == null
          ? `Each line is one territory, lightest to heaviest.${p.over > 0 ? ` ${p.over} reach past 2.0 and are cut flat; the heaviest is ${p.heaviest.toFixed(1)} times the target.` : ""}`
          : `Rank ${(rank + 1).toLocaleString("en-US")} of ${n.toLocaleString("en-US")}. Weight ${p.sorted[rank].toFixed(2)}${idByWeight ? ` (${idByWeight[rank].id})` : ""}.`}
      </p>
    </div>
  );
}

// ------------------------------------------------------------------------------------------ the reality check

export type RhoRow = { franchise: string; size: number; intensity: number };

export function RealityCheck({ rows }: { rows: RhoRow[] }) {
  const [wrap, width] = useWidth<HTMLDivElement>(520);
  const m = { top: 8, right: 28, bottom: 26, left: width < 420 ? 84 : 110 };
  const rowH = 30;
  const h = m.top + m.bottom + rows.length * 2 * rowH;
  const iw = width - m.left - m.right;
  const x = scaleLinear().domain([-1, 1]).range([0, iw]);
  return (
    <div ref={wrap}>
      <svg className="svg" viewBox={`0 0 ${width} ${h}`} width={width} height={h} role="img" aria-label="Rank correlation of the demand built from public prevalence with Medicaid drug spend by state, on a scale from minus 1 to plus 1">
        <g transform={`translate(${m.left},${m.top})`}>
          {[
            { t: -1, label: "−1" },
            { t: -0.5, label: "−0.5" },
            { t: 0, label: "0" },
            { t: 0.5, label: "0.5" },
            { t: 1, label: "1" },
          ].map(({ t, label }) => (
            <g key={t}>
              <line className={t === 0 ? "base" : "grid"} x1={x(t)} x2={x(t)} y1={0} y2={rows.length * 2 * rowH} />
              <text className="t-mute" x={x(t)} y={rows.length * 2 * rowH + 18} textAnchor="middle">
                {label}
              </text>
            </g>
          ))}
          {rows.map((r, i) => {
            const y0 = i * 2 * rowH;
            return (
              <g key={r.franchise}>
                <text className="t-strong" x={-10} y={y0 + rowH - 4} textAnchor="end">
                  {r.franchise}
                </text>
                <rect className="mk-i" x={x(r.size) - 4} y={y0 + rowH / 2 - 4} width={8} height={8} />
                <text className="t-strong" x={x(r.size) + (r.size > 0.3 ? -10 : 10)} y={y0 + rowH / 2 + 4} textAnchor={r.size > 0.3 ? "end" : "start"}>
                  {rho(r.size)} state size
                </text>
                <rect className="mk-o" x={x(r.intensity) - 4} y={y0 + rowH * 1.5 - 4} width={8} height={8} />
                <text className="t-lab" x={x(r.intensity) + (r.intensity > 0.3 ? -10 : 10)} y={y0 + rowH * 1.5 + 4} textAnchor={r.intensity > 0.3 ? "end" : "start"}>
                  {rho(r.intensity)} spend per enrollee
                </text>
              </g>
            );
          })}
        </g>
      </svg>
    </div>
  );
}

// ------------------------------------------------------------------------------------------ the reconciliation

export function Waterfall({ steps }: { steps: Step[] }) {
  const [wrap, width] = useWidth<HTMLDivElement>(700);
  const narrow = width < 560;
  const labelW = narrow ? 0 : 250;
  const rowH = narrow ? 50 : 34;
  const h = steps.length * rowH + 4;
  const max = steps[0].value;
  const x = scaleLinear().domain([0, max]).range([0, width - labelW - 110]);
  return (
    <div ref={wrap}>
      <svg className="svg" viewBox={`0 0 ${width} ${h}`} width={width} height={h} role="img" aria-label={`From ${int(steps[0].value)} registry records to ${int(steps[steps.length - 1].value)} providers placed in a county`}>
        {steps.map((s, i) => {
          const y = i * rowH;
          return (
            <g key={s.label}>
              <text className="t-lab" x={0} y={y + (narrow ? 14 : 20)}>
                {s.label}
              </text>
              <rect className="bar-i" x={labelW} y={y + (narrow ? 22 : 6)} width={Math.max(1, x(s.value))} height={18} />
              <text className="t-strong" x={labelW + x(s.value) + 8} y={y + (narrow ? 36 : 20)}>
                {int(s.value)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export function Glyph({ status }: { status: "pass" | "warn" | "fail" | "info" }) {
  const common = { width: 14, height: 14, viewBox: "0 0 14 14", "aria-hidden": true } as const;
  if (status === "pass")
    return (
      <svg {...common}>
        <path d="M2 7.5 L5.5 11 L12 3" fill="none" stroke="currentColor" strokeWidth="2" />
      </svg>
    );
  if (status === "warn")
    return (
      <svg {...common}>
        <path d="M2 7 H12" fill="none" stroke="currentColor" strokeWidth="2" />
      </svg>
    );
  if (status === "fail")
    return (
      <svg {...common}>
        <path d="M3 3 L11 11 M11 3 L3 11" fill="none" stroke="currentColor" strokeWidth="2" />
      </svg>
    );
  return (
    <svg {...common}>
      <circle cx="7" cy="7" r="4.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}
