import { useEffect, useRef, useState } from 'react';

interface Edges {
  top: boolean;
  bottom: boolean;
}

const EDGE_TOLERANCE = 4; // px slack when deciding "at edge"

/**
 * Returns a ref + boolean flags for whether content is hidden above
 * (top fade needed) or below (bottom fade needed). Use the booleans
 * to render absolutely-positioned gradient overlays — they don't
 * hide content the way mask-image does.
 */
export function useFadeMask<T extends HTMLElement = HTMLDivElement>() {
  const ref = useRef<T>(null);
  const [edges, setEdges] = useState<Edges>({ top: false, bottom: false });

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const update = () => {
      const isScrollable = el.scrollHeight - el.clientHeight > 1;
      if (!isScrollable) {
        setEdges({ top: false, bottom: false });
        return;
      }
      const atTop = el.scrollTop <= EDGE_TOLERANCE;
      const atBottom =
        el.scrollTop + el.clientHeight >= el.scrollHeight - EDGE_TOLERANCE;
      setEdges({ top: !atTop, bottom: !atBottom });
    };

    update();
    el.addEventListener('scroll', update, { passive: true });
    const ro = new ResizeObserver(update);
    ro.observe(el);
    const mo = new MutationObserver(update);
    mo.observe(el, { childList: true, subtree: true, characterData: true });

    return () => {
      el.removeEventListener('scroll', update);
      ro.disconnect();
      mo.disconnect();
    };
  }, []);

  return { ref, ...edges };
}
