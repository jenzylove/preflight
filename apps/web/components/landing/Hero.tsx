"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";

/** The public opening: one page, two deliberate cinema-delivery images. */
export function Hero() {
  const imageField = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const field = imageField.current;
    if (!field) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    let frame = 0;

    const update = () => {
      frame = 0;
      if (reduced.matches) {
        field.style.setProperty("--screening-drift", "0px");
        field.style.setProperty("--projector-drift", "0px");
        return;
      }
      const distance = Math.min(window.scrollY, window.innerHeight);
      field.style.setProperty("--screening-drift", `${-Math.min(30, distance * 0.045)}px`);
      field.style.setProperty("--projector-drift", `${-Math.min(16, distance * 0.024)}px`);
    };

    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };

    update();
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule, { passive: true });
    reduced.addEventListener("change", schedule);
    return () => {
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
      reduced.removeEventListener("change", schedule);
      if (frame) cancelAnimationFrame(frame);
    };
  }, []);

  return (
    <section className="relative min-h-[100svh] overflow-hidden bg-[#b7a9b5] text-[#382d37]" aria-labelledby="hero-heading">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_25%_28%,rgba(246,239,237,0.22),transparent_36%),linear-gradient(135deg,#b3a3b0,#c1b5bc_58%,#aa9aa8)]" aria-hidden="true" />

      <header className="relative z-30 mx-auto flex max-w-[1240px] items-center justify-between px-6 py-7 sm:px-10 lg:px-14">
        <Link href="/" className="text-[10px] font-semibold uppercase tracking-[0.3em] text-[#382d37]">
          Pre<span className="text-[#765f70]">—</span>flight
        </Link>
        <Link href="/signin" className="text-xs font-medium text-[#574653] transition hover:text-[#2c222b]">Sign in</Link>
      </header>

      <div className="relative z-10 mx-auto grid min-h-[calc(100svh-74px)] max-w-[1240px] items-center px-6 pb-20 sm:px-10 lg:grid-cols-[0.82fr_1.18fr] lg:px-14 lg:pb-16">
        <div className="relative z-20 max-w-[610px] py-20 lg:py-0">
          <h1 id="hero-heading" className="font-display text-[clamp(4.6rem,8.2vw,8.8rem)] leading-[0.82] tracking-[-0.055em] text-[#382d37]">
            Ready before<br />it leaves<br />your hands.
          </h1>
          <p className="mt-8 max-w-[32rem] text-[16px] leading-[1.65] text-[#51414e] sm:text-[17px]">
            Preflight measures a finished master against real delivery requirements, then prepares a package with the proof to travel.
          </p>
          <Link href="/projects" className="mt-9 inline-flex rounded-[4px] bg-[#3f323e] px-6 py-3.5 text-sm font-medium text-[#f1eae8] shadow-[0_12px_28px_rgba(57,42,54,0.18)] transition hover:bg-[#2f252e]">
            Prepare your film
          </Link>
        </div>

        <div ref={imageField} className="hero-image-field relative hidden h-[680px] lg:block" aria-hidden="true">
          <div className="hero-projector-image absolute right-[-3%] top-[2%] h-[330px] w-[330px] overflow-hidden rounded-[51%_49%_47%_53%/48%_52%_48%_52%] shadow-[0_28px_60px_rgba(55,39,52,0.28)]">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/film/hero-projection-v3.png" alt="" className="h-full w-full object-cover object-[62%_50%]" />
          </div>
          <div className="hero-screening-image absolute -bottom-[3%] -right-[4%] h-[450px] w-[620px] overflow-hidden rounded-[50%_50%_46%_54%/49%_44%_56%_51%] shadow-[0_36px_76px_rgba(55,39,52,0.34)]">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/film/hero-screening-v4.png" alt="" className="h-full w-full object-cover object-[48%_52%]" />
          </div>
        </div>

        <div className="relative mt-4 aspect-[1.35/1] overflow-hidden rounded-[48%_52%_48%_52%/50%_44%_56%_50%] shadow-[0_28px_60px_rgba(55,39,52,0.3)] lg:hidden" aria-hidden="true">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/film/hero-screening-v4.png" alt="" className="h-full w-full object-cover" />
        </div>
      </div>
    </section>
  );
}
