import type { MetadataRoute } from "next";
import { BRAND } from "../lib/site-metrics";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || `https://${BRAND.domain}`;

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: ["/dashboard", "/auth"],
    },
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
