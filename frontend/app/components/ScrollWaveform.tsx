"use client";

import { motion, useScroll } from "motion/react";

/**
 * The page's one authored focal moment: a voice waveform pinned to the
 * bottom edge of the nav that "plays" as you scroll -- the further down
 * the page, the more of the call has played. Ties the product's core
 * signal (a live voice call) directly to the act of scrolling, instead of
 * a generic reading-progress bar.
 *
 * Implementation is a single scaleX transform on a teal copy of the bar
 * pattern layered over a dim "unplayed" copy -- one GPU transform driven
 * by scrollYProgress, no per-frame layout work.
 */
const HEIGHTS = [
  4, 7, 3, 9, 5, 8, 4, 6, 10, 5, 3, 7, 9, 4, 6, 8, 3, 5, 7, 4, 9, 6, 3, 8,
  5, 7, 4, 9, 6, 3, 8, 5, 7, 10, 4, 6, 3, 9, 5, 7, 4, 8, 6, 3, 9, 5, 7, 4,
  6, 8, 3, 5, 9, 7, 4, 6, 3, 8, 5, 7,
];

export default function ScrollWaveform() {
  const { scrollYProgress } = useScroll();

  return (
    <div
      className="pointer-events-none absolute inset-x-0 bottom-0 h-[10px] overflow-hidden"
      aria-hidden="true"
    >
      {/* Unplayed track */}
      <div className="absolute inset-0 flex items-end gap-[2px] px-1 opacity-[0.14]">
        {HEIGHTS.map((h, i) => (
          <span
            key={i}
            className="w-[2px] shrink-0 rounded-full bg-[var(--color-ink)]"
            style={{ height: `${h}px` }}
          />
        ))}
      </div>
      {/* Played -- scales in from the left as scrollYProgress advances */}
      <motion.div
        className="absolute inset-0 flex origin-left items-end gap-[2px] px-1"
        style={{ scaleX: scrollYProgress }}
      >
        {HEIGHTS.map((h, i) => (
          <span
            key={i}
            className="w-[2px] shrink-0 rounded-full bg-[var(--color-signal)]"
            style={{ height: `${h}px` }}
          />
        ))}
      </motion.div>
    </div>
  );
}
