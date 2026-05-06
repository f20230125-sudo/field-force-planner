"use client";

import { useMemo, useRef, useState, type PointerEvent } from "react";
import { readout } from "@/lib/derive";
import type { AlignFranchise, Counties, Franchise, MapData } from "@/lib/schema";
import { Tip, useTip, useWidth } from "./chart";

type Props = {
  map: MapData | null;
  counties: Counties;
  align: AlignFranchise;
  franchise: Franchise;
  zoom: string;
};

const PAD = 24;

/**
 * The county map: one shape per county tinted by territory (colour only says "different from the neighbour"), an ink line
 * wherever a territory changes, hatching on counties cut between territories, state lines for orientation. Hover, tap or
 * the state select reads a county in words; the same text goes into a polite live region under the map.
 */
export function TerritoryMap(props: Props) {
  const { map } = props;
  if (!map) {
    return (
      <div className="map" style={{ minHeight: 320 }}>
        <p className="readout" aria-live="polite">Loading the map shapes.</p>
      </div>
    );
  }
  return <LoadedMap {...props} map={map} />;
}

function LoadedMap({ map, counties, align, franchise, zoom }: Props & { map: MapData }) {
  const [wrap, width] = useWidth<HTMLDivElement>(860);
  const host = useRef<HTMLDivElement | null>(null);
  const { tip, atPointer, hide } = useTip(host);
  const [pick, setPick] = useState<number | null>(null);
  const f = counties[franchise];
  const [, , vw, vh] = map.viewBox;

  const view = useMemo((): [number, number, number, number] => {
    const b = map.stateBoxes[zoom];
    if (!b) return map.viewBox;
    const w = b[2] - b[0] + 2 * PAD;
    const h = b[3] - b[1] + 2 * PAD;
    const k = Math.max(w / vw, h / vh); // keep the map's aspect ratio so shapes are not stretched
    const W = vw * k;
    const H = vh * k;
    return [b[0] - PAD - (W - w) / 2, b[1] - PAD - (H - h) / 2, W, H];
  }, [map, zoom, vw, vh]);

  const hatched = useMemo(() => map.d.filter((_, i) => f.touching[map.row[i]] > 1).join(""), [map, f]);
  const merged = (i: number) => map.ids[i] === "02261";
  const text = (i: number) => readout(counties, align, franchise, map.row[i], merged(i));

  const at = (e: PointerEvent<SVGGElement>): number | null => {
    const v = (e.target as SVGElement).getAttribute?.("data-i");
    return v == null ? null : Number(v);
  };
  const onMove = (e: PointerEvent<SVGGElement>) => {
    const i = at(e);
    if (i == null) return hide();
    const r = text(i);
    atPointer(r.title, [{ label: r.text, value: "" }])(e);
  };
  const onTap = (e: PointerEvent<SVGGElement>) => {
    const i = at(e);
    if (i != null) setPick(i);
  };
  const r = pick == null ? null : text(pick);
  const ratio = vh / vw;

  return (
    <div className="map" ref={host}>
      <div ref={wrap}>
        <svg
          viewBox={view.join(" ")}
          width={width}
          height={Math.round(width * ratio)}
          role="img"
          aria-label={`County map of the ${align.territories.toLocaleString("en-US")} ${franchise} territories. Colour only tells neighbouring territories apart; a line marks where one territory ends and the next begins.`}
        >
          <defs>
            <pattern id="hatch" width="4.5" height="4.5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <line x1="0" y1="0" x2="0" y2="4.5" stroke="var(--ink)" strokeWidth="0.6" vectorEffect="non-scaling-stroke" />
            </pattern>
          </defs>
          <g onPointerMove={onMove} onPointerLeave={hide} onPointerDown={onTap}>
            {map.d.map((d, i) => (
              <path key={map.ids[i]} data-i={i} className={`county t${f.colour[map.row[i]]}`} d={d} />
            ))}
          </g>
          <path className="hatch" d={hatched} />
          <path className="cut" d={map.cut[franchise]} />
          <path className="st" d={map.states} />
          <path className="nation" d={map.nation} />
          {pick != null && <path className="sel" d={map.d[pick]} />}
        </svg>
      </div>
      <p className="readout" aria-live="polite">
        {r ? (
          <>
            <b>{r.title}.</b> {r.text}
          </>
        ) : (
          "Hover or tap a county to read its territory. The state select zooms to one state."
        )}
      </p>
      <Tip tip={tip} width={width} />
    </div>
  );
}
