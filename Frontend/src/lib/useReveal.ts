import { useEffect, useState } from "react";

/**
 * Reveals the children of every `.stagger` container as they scroll into view: each gets
 * data-reveal="in" (styles.css plays the rise-in), with --reveal-order counting the ones that appear
 * together, so they come in one after another. New cards, e.g. after data loads, are picked up too.
 *
 * Returns whether it's running. Until then, and with "reduce motion" or no IntersectionObserver,
 * nothing is hidden, so the page never depends on this script to be visible.
 */
export function useReveal(): boolean {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (reduced || !("IntersectionObserver" in window)) return;

    const observer = new IntersectionObserver(
      (entries) => {
        let order = 0;
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          const el = entry.target as HTMLElement;
          el.style.setProperty("--reveal-order", String(order++));
          el.dataset["reveal"] = "in";
          observer.unobserve(el);
        }
      },
      { rootMargin: "0px 0px -6% 0px", threshold: 0.05 },
    );
    const watch = () =>
      document.querySelectorAll<HTMLElement>(".stagger > :not([data-reveal])").forEach((el) => observer.observe(el));

    watch();
    const mutations = new MutationObserver(watch);
    mutations.observe(document.body, { childList: true, subtree: true });
    setReady(true);
    return () => {
      observer.disconnect();
      mutations.disconnect();
    };
  }, []);

  return ready;
}
