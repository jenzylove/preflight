"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Scroll progress through an element, 0 to 1, sampled on animation frames.
 *
 * Deliberately not a library. The hero needs one number, and a scroll listener
 * that writes to a ref and reads on rAF is both smaller and steadier than
 * anything that would ship for this. Every consumer transforms the same value,
 * so the whole sequence stays in sync by construction.
 */
export function useScrollProgress<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;

    // With motion reduced the sequence is presented as a static diagram, so
    // there is nothing to drive and no reason to listen to scroll at all.
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (reduced.matches) {
      setProgress(0);
      return;
    }

    let frame = 0;
    let latest = 0;

    const measure = () => {
      const rect = element.getBoundingClientRect();
      const travel = rect.height - window.innerHeight;
      if (travel <= 0) {
        latest = 0;
        return;
      }
      latest = Math.min(1, Math.max(0, -rect.top / travel));
    };

    const tick = () => {
      frame = 0;
      setProgress((current) =>
        Math.abs(current - latest) < 0.0005 ? current : latest,
      );
    };

    const onScroll = () => {
      measure();
      if (!frame) frame = requestAnimationFrame(tick);
    };

    measure();
    setProgress(latest);

    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (frame) cancelAnimationFrame(frame);
    };
  }, []);

  return { ref, progress };
}

/** Map a value from one range to another, clamped at both ends. */
export function range(
  value: number,
  inMin: number,
  inMax: number,
  outMin = 0,
  outMax = 1,
) {
  if (inMax === inMin) return outMin;
  const t = Math.min(1, Math.max(0, (value - inMin) / (inMax - inMin)));
  return outMin + (outMax - outMin) * t;
}

/** Slow in, slow out. Closer to a dolly move than to a UI transition. */
export function ease(t: number) {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

/** Whether the viewer has asked for less motion, for render-time branching. */
export function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(query.matches);
    const onChange = () => setReduced(query.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);
  return reduced;
}
