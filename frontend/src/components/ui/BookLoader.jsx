import { useEffect, useRef } from "react";

/*
 * Animated bookshelf loader (adapted from Uiverse.io by MMonograma): a book slides
 * off the shelf, opens, flips its pages, and goes back. Shown while an answer is
 * being retrieved and written. The SVG animation is paused for reduced-motion users.
 */

const SPLINE = ".45 0 .25 1";

function Animate({ type, keyTimes, values, additive }) {
  const segments = values.split(";").length - 1;
  return (
    <animateTransform
      attributeName="transform"
      type={type}
      dur="5s"
      repeatCount="indefinite"
      keyTimes={keyTimes}
      values={values}
      keySplines={Array(segments).fill(SPLINE).join(";")}
      additive={additive}
    />
  );
}

const COVER_FLIP = { keyTimes: "0;.16;.24;.56;.66;1", values: "1 1;1 1;-1 1;-1 1;1 1;1 1" };
const COVER_BEND = { keyTimes: "0;.16;.20;.24;.56;.61;.66;1", values: "0;0;-5;0;0;-5;0;0" };

function Paper({ lines = true }) {
  return (
    <>
      <rect className="fill-amber-50" x="0" y="87" width="41" height="50" rx="3" />
      <rect className="fill-stone-400" x="0" y="87" width="4" height="50" opacity=".25" />
      {lines && (
        <path
          className="stroke-stone-300"
          strokeWidth="1.2"
          strokeLinecap="round"
          d="M7 97h27M7 103h27M7 109h24M7 115h27M7 121h27M7 127h18"
        />
      )}
    </>
  );
}

/** One page turning between `start` and `end` (fractions of the 5 s loop). */
function TurningPage({ start, end }) {
  const mid = (start + end) / 2;
  return (
    <g>
      <Animate type="scale" keyTimes={`0;${start};${end};.56;.66;1`} values="1 1;1 1;-1 1;-1 1;1 1;1 1" />
      <Animate type="skewY" keyTimes={`0;${start};${mid};${end};1`} values="0;0;-5;0;0" additive="sum" />
      <Paper />
    </g>
  );
}

function Shelf() {
  return (
    <>
      <ellipse className="fill-black" cx="102" cy="153" rx="58" ry="3" opacity=".12" />
      <rect className="fill-emerald-700" x="52" y="92" width="12" height="48" rx="3" />
      <rect className="fill-white" x="55" y="94" width="2.5" height="44" rx="1.2" opacity=".18" />
      <rect className="fill-sky-700" x="66" y="80" width="16" height="60" rx="3" />
      <rect className="fill-white" x="70" y="82" width="3" height="56" rx="1.5" opacity=".18" />
      <rect className="fill-sky-200" x="69" y="90" width="10" height="5" rx="2.5" opacity=".45" />
      <rect className="fill-amber-600" x="85" y="88" width="12" height="52" rx="3" />
      <rect className="fill-white" x="88" y="90" width="2.5" height="48" rx="1.2" opacity=".2" />
      <rect className="fill-indigo-700" x="117" y="84" width="16" height="56" rx="3" />
      <rect className="fill-white" x="121" y="86" width="3" height="52" rx="1.5" opacity=".18" />
      <rect className="fill-indigo-200" x="119" y="128" width="12" height="2" rx="1" opacity=".5" />
      <rect className="fill-teal-700" x="136" y="96" width="12" height="44" rx="3" />
      <rect className="fill-white" x="139" y="98" width="2.5" height="40" rx="1.2" opacity=".18" />
      <g transform="rotate(14 150 140)">
        <rect className="fill-orange-600" x="150" y="86" width="12" height="54" rx="3" />
        <rect className="fill-white" x="153" y="88" width="2.5" height="50" rx="1.2" opacity=".2" />
      </g>
    </>
  );
}

function BookSpine() {
  return (
    <g>
      <Animate type="scale" keyTimes="0;.10;.16;.68;.74;1" values="1 1;1 1;0.001 1;0.001 1;1 1;1 1" />
      <rect className="fill-rose-700" x="0" y="84" width="14" height="56" rx="3" />
      <rect className="fill-black" x="9" y="84" width="5" height="56" rx="2" opacity=".2" />
      <rect className="fill-white" x="3" y="86" width="2.5" height="52" rx="1.2" opacity=".2" />
      <rect className="fill-amber-300" x="2" y="92" width="10" height="2" rx="1" />
      <rect className="fill-amber-300" x="2" y="96" width="10" height="1.5" rx=".75" opacity=".6" />
      <rect className="fill-amber-300" x="2" y="130" width="10" height="2" rx="1" />
    </g>
  );
}

function OpenBook() {
  return (
    <g>
      <Animate type="scale" keyTimes="0;.10;.16;.68;.74;1" values="0.001 1;0.001 1;1 1;1 1;0.001 1;0.001 1" />
      {/* back cover and the page underneath */}
      <rect className="fill-rose-800" x="0" y="84" width="44" height="56" rx="4" />
      <Paper />

      {/* inside of the front cover */}
      <g>
        <Animate type="scale" {...COVER_FLIP} />
        <Animate type="skewY" {...COVER_BEND} additive="sum" />
        <rect className="fill-rose-800" x="0" y="84" width="44" height="56" rx="4" />
        <Paper lines={false} />
      </g>

      <TurningPage start={0.42} end={0.5} />
      <TurningPage start={0.34} end={0.42} />
      <TurningPage start={0.26} end={0.34} />

      {/* front cover */}
      <g>
        <Animate type="scale" {...COVER_FLIP} />
        <Animate type="skewY" {...COVER_BEND} additive="sum" />
        <rect className="fill-rose-700" x="0" y="84" width="44" height="56" rx="4" />
        <rect className="fill-rose-900" x="22" y="84" width="22" height="56" rx="4" opacity=".35" />
        <rect className="fill-black" x="0" y="84" width="5" height="56" rx="2" opacity=".18" />
        <rect className="stroke-amber-300" x="9" y="90" width="29" height="44" rx="3" fill="none" strokeWidth="1.2" opacity=".7" />
        <rect className="fill-amber-300" x="14" y="98" width="19" height="2.5" rx="1.25" opacity=".9" />
        <rect className="fill-amber-300" x="17" y="104" width="13" height="2" rx="1" opacity=".55" />
      </g>
    </g>
  );
}

export function BookLoader({ label = "Searching your library" }) {
  const svgRef = useRef(null);

  useEffect(() => {
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) svgRef.current?.pauseAnimations?.();
  }, []);

  return (
    <div role="status" aria-label={label} className="flex flex-col items-center gap-3 py-4">
      <svg ref={svgRef} viewBox="30 14 140 142" className="h-48 w-48 overflow-visible" aria-hidden="true">
        <Shelf />
        {/* the book: slides up off the shelf, opens, turns pages, closes and returns */}
        <g>
          <Animate type="translate" keyTimes="0;.02;.11;.76;.88;1" values="0 0;0 0;0 -62;0 -62;0 0;0 0" />
          <g transform="translate(100 0)">
            <BookSpine />
            <OpenBook />
          </g>
        </g>
        <rect className="fill-amber-800" x="40" y="140" width="124" height="9" rx="4.5" />
        <rect className="fill-amber-600" x="44" y="140" width="116" height="2" rx="1" />
      </svg>
      <span className="animate-pulse text-xs font-medium tracking-[0.2em] text-stone-500 uppercase motion-reduce:animate-none">
        {label}
      </span>
    </div>
  );
}
