import { useEffect, useRef } from "react";

const TARGET_ID = "WidgetPlaceHolder";

// The loader ships no list styling and its markup is not ours, so the table view is styled
// from the wrapper with arbitrary variants.
const TABLE_STYLES = [
  "[&_.SearchResultHeader]:mb-3 [&_.SearchResultHeader_img]:h-10 [&_.SearchResultHeader_img]:w-auto",
  "[&_.SearchResultMatchList]:flex [&_.SearchResultMatchList]:flex-col [&_.SearchResultMatchList]:gap-2.5",
  "[&_.SearchResultMatch]:grid [&_.SearchResultMatch]:grid-cols-[48px_minmax(0,1fr)] sm:[&_.SearchResultMatch]:grid-cols-[72px_minmax(0,1fr)]",
  "[&_.SearchResultMatch]:items-start [&_.SearchResultMatch]:gap-4 [&_.SearchResultMatch]:rounded-xl [&_.SearchResultMatch]:border [&_.SearchResultMatch]:p-4",
  "[&_.SearchResultMatch:nth-child(odd)]:bg-wash [&_.SearchResultMatch:nth-child(even)]:bg-card",
  "[&_.SearchResultColLeft_img]:block [&_.SearchResultColLeft_img]:size-12 sm:[&_.SearchResultColLeft_img]:size-[72px] [&_.SearchResultColLeft_img]:rounded-[10px] [&_.SearchResultColLeft_img]:bg-white [&_.SearchResultColLeft_img]:object-contain",
  "[&_.SearchResultColRight]:flex [&_.SearchResultColRight]:min-w-0 [&_.SearchResultColRight]:flex-col [&_.SearchResultColRight]:gap-1.5",
  "[&_.SearchResultItemTitle]:font-bold [&_.SearchResultItemTitle]:leading-snug [&_.SearchResultItemTitle]:break-words [&_.SearchResultItemTitle_a]:text-primary",
  "[&_.SearchResultItemTeaser]:text-sm [&_.SearchResultItemTeaser]:leading-normal [&_.SearchResultItemTeaser]:text-muted-foreground",
  "[&_.SearchResultItemLastUpdateDate]:text-xs [&_.SearchResultItemLastUpdateDate]:text-muted-foreground",
  "[&_.SearchResultAppliDomIconList:empty]:hidden",
  "[&_.SearchResultPagination]:mt-5 [&_.SearchResultPagination]:flex [&_.SearchResultPagination]:justify-center",
  "[&_.SearchResultPagination_ul]:m-0 [&_.SearchResultPagination_ul]:flex [&_.SearchResultPagination_ul]:list-none [&_.SearchResultPagination_ul]:flex-wrap [&_.SearchResultPagination_ul]:justify-center [&_.SearchResultPagination_ul]:gap-1.5 [&_.SearchResultPagination_ul]:p-0",
  "[&_.SearchResultPagination_li_:is(a,span)]:grid [&_.SearchResultPagination_li_:is(a,span)]:h-[34px] [&_.SearchResultPagination_li_:is(a,span)]:min-w-[34px] [&_.SearchResultPagination_li_:is(a,span)]:cursor-pointer [&_.SearchResultPagination_li_:is(a,span)]:place-items-center [&_.SearchResultPagination_li_:is(a,span)]:rounded-md [&_.SearchResultPagination_li_:is(a,span)]:border [&_.SearchResultPagination_li_:is(a,span)]:px-2.5 [&_.SearchResultPagination_li_:is(a,span)]:text-[13px] [&_.SearchResultPagination_li_:is(a,span)]:font-bold [&_.SearchResultPagination_li_:is(a,span)]:text-primary",
  "[&_.SearchResultPagination_li_.current]:cursor-default [&_.SearchResultPagination_li_.current]:border-primary [&_.SearchResultPagination_li_.current]:bg-primary [&_.SearchResultPagination_li_.current]:text-primary-foreground",
  "[&_.SearchResultPagination_li_:is(.disabled,.ellipse)]:cursor-default [&_.SearchResultPagination_li_:is(.disabled,.ellipse)]:opacity-50",
  "[&_.SearchResultFooter]:mt-4 [&_.SearchResultFooter]:text-center [&_.SearchResultFooter]:text-xs [&_.SearchResultFooter]:text-muted-foreground",
].join(" ");

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

  return <div ref={hostRef} className={output === "table" ? TABLE_STYLES : undefined} />;
}
