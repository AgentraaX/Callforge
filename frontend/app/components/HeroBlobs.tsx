"use client";

import { useRef } from "react";
import { motion, useScroll, useTransform } from "motion/react";

/** Scroll-linked parallax on the hero's decorative background blobs --
 * the two layers drift at different rates as the hero scrolls past,
 * giving the background a sense of depth instead of sitting flat. */
export default function HeroBlobs() {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start start", "end start"],
  });

  const yBack = useTransform(scrollYProgress, [0, 1], [0, 140]);
  const yFront = useTransform(scrollYProgress, [0, 1], [0, 260]);

  return (
    <div ref={ref} className="absolute inset-0 overflow-hidden" aria-hidden="true">
      <motion.div className="blob-teal -top-40 -left-40" style={{ y: yBack }} />
      <motion.div className="blob-cyan top-20 right-0" style={{ y: yFront }} />
    </div>
  );
}
