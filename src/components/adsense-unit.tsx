"use client";

import { useEffect } from "react";

type AdsenseWindow = Window & { adsbygoogle?: unknown[] };

export function AdsenseUnit({ client, slot }: { client: string; slot: string }) {
  useEffect(() => {
    try {
      const adsenseWindow = window as AdsenseWindow;
      adsenseWindow.adsbygoogle = adsenseWindow.adsbygoogle || [];
      adsenseWindow.adsbygoogle.push({});
    } catch {
      // The ads script can reject a second push while it is still loading.
    }
  }, []);

  return (
    <ins
      className="adsbygoogle"
      style={{ display: "block" }}
      data-ad-client={client}
      data-ad-slot={slot}
      data-ad-format="auto"
      data-full-width-responsive="true"
    />
  );
}
