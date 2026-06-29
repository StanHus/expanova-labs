"use client";

import { useEffect, useRef } from "react";

/**
 * Reveal — sets data-revealed="true" on first scroll-into-view.
 * - fade: also fades/translates the wrapper itself (data-reveal).
 * - child elements with .bar-grow / .bar-grow-x / .rule-verified animate
 *   via the ancestor [data-revealed="true"] selectors in globals.css.
 */
export default function Reveal({
  children,
  className,
  fade = false,
  stagger,
  as = "div",
}: {
  children: React.ReactNode;
  className?: string;
  fade?: boolean;
  stagger?: 1 | 2 | 3;
  as?: "div" | "section" | "li";
}) {
  const ref = useRef<HTMLElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (typeof IntersectionObserver === "undefined") {
      el.setAttribute("data-revealed", "true");
      return;
    }
    const io = new IntersectionObserver(
      (entries) =>
        entries.forEach((e) => {
          if (e.isIntersecting) {
            el.setAttribute("data-revealed", "true");
            io.unobserve(el);
          }
        }),
      { threshold: 0.12, rootMargin: "0px 0px -6% 0px" }
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  const Tag = as as "div";
  return (
    <Tag
      ref={ref as React.RefObject<HTMLDivElement>}
      className={className}
      {...(fade ? { "data-reveal": "" } : {})}
      {...(stagger ? { "data-reveal-stagger": String(stagger) } : {})}
    >
      {children}
    </Tag>
  );
}
