import { type CSSProperties } from "react";
import { useQuery } from "@tanstack/react-query";
import { Layers3 } from "lucide-react";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { getApiBaseUrl } from "@/config/runtime";
import "./premium-launcher.css";

export type BannerAppearance = {
  image: string; mobile_image: string; x: number; y: number;
  mobile_x: number; mobile_y: number; zoom: number; overlay: string; opacity: number;
};
export const defaultBanner: BannerAppearance = {
  image: "/images/suite-office-hero.webp", mobile_image: "", x: 70, y: 50,
  mobile_x: 75, mobile_y: 50, zoom: 1, overlay: "#eeedff", opacity: 0.15,
};
export function bannerImageUrl(image: string) {
  return image.startsWith("asset:") ? `${getApiBaseUrl()}/auth/homepage-banner/assets/${image.slice(6)}` : image;
}
export function useHomepageBanner() {
  const { user, isAuthenticated } = useAuthStore();
  const company = sessionStorage.getItem("suite-organization") || user?.access?.companyId;
  return useQuery({ queryKey: ["homepage-banner", isAuthenticated ? user?.id : "public", company],
    queryFn: () => api.get<BannerAppearance>(isAuthenticated ? "/access/homepage-banner" : "/auth/homepage-banner", { progress: false }).then(r => r.data), staleTime: 60_000 });
}
export default function HomepageBanner({ appearance, company, preview = false, onImageError }: { appearance?: BannerAppearance; company?: string; preview?: boolean; onImageError?: () => void }) {
  const settings = useHomepageBanner();
  const value = appearance || settings.data || defaultBanner;
  const image = bannerImageUrl(value.image);
  return <section className={`launcher-hero${preview ? " launcher-banner-preview" : ""}`} style={{
    "--banner-x": `${value.x}%`, "--banner-y": `${value.y}%`, "--banner-mobile-x": `${value.mobile_x}%`,
    "--banner-mobile-y": `${value.mobile_y}%`, "--banner-zoom": value.zoom,
  } as CSSProperties}>
    {image && <picture className="launcher-hero-image">
      {value.mobile_image && <source media="(max-width: 767px)" srcSet={bannerImageUrl(value.mobile_image)} />}
      <img src={image} alt="" loading="eager" referrerPolicy="no-referrer" onLoad={e => { e.currentTarget.style.visibility = "visible"; }} onError={e => { e.currentTarget.style.visibility = "hidden"; onImageError?.(); }} />
    </picture>}
    <div className="launcher-hero-tint" style={{ background: value.overlay, opacity: value.opacity }} />
    <div className="launcher-hero-wash" />
    <div className="launcher-hero-content">
      <p className="launcher-pill"><Layers3 size={19} />{company || "One account. Six connected applications."}</p>
      <h1>Your work <span>starts here.</span></h1>
      <p>{company ? "Choose an application to get started. Move between your roles with one Business Suite account." : "Explore your applications, then sign in with your Business Suite account. Your organization determines which applications you can access."}</p>
    </div>
  </section>;
}
