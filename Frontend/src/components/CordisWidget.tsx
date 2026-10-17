import { useEffect, useRef } from "react";

const TARGET_ID = "WidgetPlaceHolder";

// Embeds the CORDIS data-lab widget. Its loader reads its own <script> tag's data-* attributes,
// so the tag is injected by hand (React would not execute a <script> rendered in JSX).
export function CordisWidget({ output }: { output: "map" | "table" }) {
  const hostRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const placeholder = document.createElement("div");
    placeholder.id = TARGET_ID;
    if (output === "map") placeholder.style.cssText = "height:420px;width:100%;";
    const script = document.createElement("script");
    script.src = "https://cordis.europa.eu/datalab/visualisations/widget/js/widgetLoader.js";
    const attrs: Record<string, string> = {
      "data-output": output,
      "data-detailledView": "on",
      "data-target": TARGET_ID,
      "data-css":
        "https://cordis.europa.eu/datalab/visualisations/widget/css/widgetSearchResultMap.css",
      "data-query": "Ocean AND BLUE AND ECONOMY",
      "data-nbi": output === "map" ? "10" : "25",
      "data-sort": "contentUpdateDate:decreasing",
      "data-type": "search-html",
      "data-lv": "en",
      "data-apikey": "e0652da8-0328-4596-b149-4469ee6c6e97",
    };
    for (const [k, v] of Object.entries(attrs)) script.setAttribute(k, v);
    host.append(script, placeholder);
    return () => host.replaceChildren();
  }, [output]);

  return <div ref={hostRef} className={output === "table" ? "cordis-table" : undefined} />;
}
