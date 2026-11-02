import { useEffect, useRef } from "react";

export function useFittingPageSize(hasDocuments: boolean, onPageSizeChange: (pageSize: number) => void) {
  const panelRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const panel = panelRef.current;
    if (!panel || !hasDocuments) return;

    function measurePageSize() {
      const list = panel?.querySelector("ul");
      const item = list?.firstElementChild;
      const pagination = panel?.querySelector("nav");
      if (!panel || !list || !item || !pagination) return;
      const itemHeight = item.getBoundingClientRect().height;
      if (itemHeight === 0) return;

      const gap = Number.parseFloat(getComputedStyle(list).rowGap) || 0;
      const footerHeight = pagination.getBoundingClientRect().height;
      const footerMargin = Number.parseFloat(getComputedStyle(pagination).marginTop) || 0;
      const footer = pagination.parentElement;
      const footerPadding = footer ? Number.parseFloat(getComputedStyle(footer).paddingBottom) || 0 : 0;
      const main = panel.closest("main");
      const bottomPadding = main ? Number.parseFloat(getComputedStyle(main).paddingBottom) || 0 : 0;
      const listTop = list.getBoundingClientRect().top + window.scrollY;
      const viewportHeight = window.visualViewport?.height ?? window.innerHeight;
      const availableHeight = viewportHeight - listTop - footerHeight - footerMargin - footerPadding - bottomPadding;
      const itemsThatFit = Math.floor((availableHeight + gap) / (itemHeight + gap));

      onPageSizeChange(Math.max(1, Math.min(100, itemsThatFit)));
    }

    measurePageSize();
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(measurePageSize);
    const pagination = panel.querySelector("nav");
    if (pagination) observer?.observe(pagination);
    if (panel.firstElementChild) observer?.observe(panel.firstElementChild);
    window.addEventListener("resize", measurePageSize);
    window.visualViewport?.addEventListener("resize", measurePageSize);

    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", measurePageSize);
      window.visualViewport?.removeEventListener("resize", measurePageSize);
    };
  }, [hasDocuments, onPageSizeChange]);

  return panelRef;
}
