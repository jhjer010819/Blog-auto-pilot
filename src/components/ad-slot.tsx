import Script from "next/script";
import { AdsenseUnit } from "./adsense-unit";

const CLIENT = process.env.NEXT_PUBLIC_ADSENSE_CLIENT ?? "";

function slotFor(position: "top" | "bottom") {
  const slot =
    position === "top"
      ? process.env.NEXT_PUBLIC_ADSENSE_SLOT_TOP
      : process.env.NEXT_PUBLIC_ADSENSE_SLOT_BOTTOM;
  if (!/^ca-pub-\d{8,20}$/.test(CLIENT) || !slot || !/^\d{8,20}$/.test(slot)) {
    return null;
  }
  return { client: CLIENT, slot };
}

export function AdSlot({ position }: { position: "top" | "bottom" }) {
  const config = slotFor(position);
  if (!config) {
    const label =
      position === "top" ? "Google Adsense Banner (Top)" : "Google Adsense Banner (Bottom)";
    return <div className="ad-slot">{label}</div>;
  }

  return (
    <div className="ad-slot ad-slot-live">
      <Script
        id="adsbygoogle-js"
        async
        strategy="afterInteractive"
        src={`https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${config.client}`}
        crossOrigin="anonymous"
      />
      <AdsenseUnit client={config.client} slot={config.slot} />
    </div>
  );
}
