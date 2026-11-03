import { NativeSelect } from "@/components/ui/native-select";
import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ImagePlus, Monitor, RotateCcw, Save, Smartphone, Upload } from "lucide-react";
import { api } from "@/services/api";
import HomepageBanner, { type BannerAppearance, defaultBanner, useHomepageBanner } from "@/components/suite/HomepageBanner";
import "./homepage-banner-settings.css";

const limit = 5 * 1024 * 1024;
export default function HomepageBannerSettings() {
  const settings = useHomepageBanner();
  const qc = useQueryClient();
  const [draft, setDraft] = useState<BannerAppearance>(defaultBanner);
  const [mobile, setMobile] = useState(false);
  const [url, setUrl] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [localImages, setLocalImages] = useState<Record<string, string>>({});
  const objectUrls = useRef<string[]>([]);
  const drag = useRef<{ x: number; y: number; left: number; top: number } | null>(null);
  useEffect(() => { if (settings.data) setDraft(settings.data); }, [settings.data]);
  useEffect(() => () => objectUrls.current.forEach(URL.revokeObjectURL), []);
  const patch = (values: Partial<BannerAppearance>) => { setDraft(d => ({ ...d, ...values })); setMessage(""); };
  const select = (image: string) => patch(mobile ? { mobile_image: image } : { image });
  const xKey = mobile ? "mobile_x" : "x";
  const yKey = mobile ? "mobile_y" : "y";
  const current = mobile ? draft.mobile_image || draft.image : draft.image;
  const preview = { ...draft, image: localImages[current] || current, mobile_image: "", x: draft[xKey], y: draft[yKey] };
  const error = (err: unknown) => {
    const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
    return typeof detail === "string" ? detail : "The banner could not be saved. Check the image and try again.";
  };
  async function upload(file?: File) {
    if (!file) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type) || file.size > limit) { setMessage("Choose a JPEG, PNG or WebP image up to 5 MB."); return; }
    setBusy(true); setMessage("");
    try {
      const data = new FormData(); data.append("file", file);
      const result = await api.post<{ image: string }>("/access/homepage-banner/upload", data, { uploadLimitBytes: limit });
      const local = URL.createObjectURL(file); objectUrls.current.push(local);
      setLocalImages(images => ({ ...images, [result.data.image]: local })); select(result.data.image);
    } catch (err) { setMessage(error(err)); } finally { setBusy(false); }
  }
  if (settings.isPending) return <p role="status">Loading banner appearance…</p>;
  if (settings.isError) return <div role="alert">Could not load the banner. <button onClick={() => void settings.refetch()}>Retry</button></div>;
  return <section className="banner-editor settings-panel">
    <div className="banner-editor-heading"><div><p className="settings-eyebrow">APPEARANCE</p><h2>Homepage Banner</h2><p>Customize the welcome banner for everyone in this company.</p></div><div className="banner-device"><button aria-pressed={!mobile} onClick={() => setMobile(false)}><Monitor size={16} />Desktop</button><button aria-pressed={mobile} onClick={() => setMobile(true)}><Smartphone size={16} />Mobile</button></div></div>
    <div className={`banner-crop ${mobile ? "banner-crop-mobile" : ""}`} aria-label="Banner crop preview. Drag to reposition, or use the positioning sliders." onPointerDown={e => { if (e.button !== 0) return; e.currentTarget.setPointerCapture(e.pointerId); drag.current = { x: e.clientX, y: e.clientY, left: draft[xKey], top: draft[yKey] }; }} onPointerMove={e => {
      if (!drag.current) return;
      const box = e.currentTarget.getBoundingClientRect();
      patch({ [xKey]: Math.max(0, Math.min(100, drag.current.left - (e.clientX - drag.current.x) / box.width * 100)), [yKey]: Math.max(0, Math.min(100, drag.current.top - (e.clientY - drag.current.y) / box.height * 100)) });
    }} onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }}>
      <HomepageBanner appearance={preview} preview onImageError={() => setMessage("This image could not be loaded. Choose another image or check the URL.")} />
      <span className="banner-crop-hint">Drag to reposition · Preview</span>
    </div>
    <p className="banner-editor-help">The frame crops the image while preserving its proportions. Adjust the zoom and position to choose the visible area.</p>
    <div className="banner-editor-columns"><div>
      <h3><ImagePlus size={18} />{mobile ? "Mobile image" : "Banner image"}</h3>
      <div className="banner-gallery">{[{ image: defaultBanner.image, title: "Glass office" }, { image: "/images/karya-login-hero.webp", title: "City workspace" }].map(item => <button key={item.image} aria-pressed={current === item.image} onClick={() => select(item.image)}><img src={item.image} alt="" /><span>{item.title}</span></button>)}</div>
      <label className="banner-upload"><Upload size={18} />Upload an image<input type="file" accept="image/jpeg,image/png,image/webp" disabled={busy} onChange={e => { void upload(e.target.files?.[0]); e.target.value = ""; }} /></label>
      <p className="banner-editor-help">JPEG, PNG or WebP · Up to 5 MB · Optimized automatically</p>
      <label className="banner-url">External image URL<input type="url" placeholder="https://example.com/banner.webp" value={url} onChange={e => setUrl(e.target.value)} /></label>
      <button className="banner-secondary" onClick={() => {
        try { const value = new URL(url); if (value.protocol !== "https:" || value.username || value.password || !value.hostname.includes(".") || /(^127\.|^10\.|^192\.168\.|\.local$|\.internal$|\.localhost$)/.test(value.hostname)) throw new Error(); select(value.href); }
        catch { setMessage("Enter a public HTTPS image URL."); }
      }}>Use URL</button>
      <div className="banner-editor-actions"><button className="banner-secondary" onClick={() => select("")}>Remove image</button>{mobile && <button className="banner-secondary" onClick={() => patch({ mobile_image: "" })}>Use desktop image</button>}</div>
    </div><div className="banner-adjustments">
      <h3>Crop & position</h3>
      <label htmlFor="banner-x">Horizontal position <output>{Math.round(draft[xKey])}%</output><input id="banner-x" type="range" min="0" max="100" value={draft[xKey]} onChange={e => patch({ [xKey]: Number(e.target.value) })} /></label>
      <label htmlFor="banner-y">Vertical position <output>{Math.round(draft[yKey])}%</output><input id="banner-y" type="range" min="0" max="100" value={draft[yKey]} onChange={e => patch({ [yKey]: Number(e.target.value) })} /></label>
      <label htmlFor="banner-zoom">Image zoom <output>{draft.zoom.toFixed(2)}×</output><input id="banner-zoom" type="range" min="1" max="3" step="0.05" value={draft.zoom} onChange={e => patch({ zoom: Number(e.target.value) })} /></label>
      <label>Image alignment<NativeSelect value={draft[xKey] === 0 ? "left" : draft[xKey] === 100 ? "right" : "center"} onChange={e => patch({ [xKey]: e.target.value === "left" ? 0 : e.target.value === "right" ? 100 : 50 })}><option value="left">Left</option><option value="center">Center</option><option value="right">Right</option></NativeSelect></label>
      <h3>Gradient overlay</h3>
      <label className="banner-color">Overlay color<input type="color" value={draft.overlay} onChange={e => patch({ overlay: e.target.value })} /></label>
      <label htmlFor="banner-opacity">Overlay opacity <output>{Math.round(draft.opacity * 100)}%</output><input id="banner-opacity" type="range" min="0" max="1" step="0.01" value={draft.opacity} onChange={e => patch({ opacity: Number(e.target.value) })} /></label>
    </div></div>
    <div className="banner-save-row"><button className="banner-secondary" disabled={busy} onClick={() => { setDraft(defaultBanner); setMessage("Default restored in preview. Save to apply."); }}><RotateCcw size={16} />Reset to default</button><button className="settings-primary" disabled={busy} onClick={async () => {
      setBusy(true); setMessage("");
      try { await api.put("/access/homepage-banner", draft); await qc.invalidateQueries({ queryKey: ["homepage-banner"] }); setMessage("Homepage banner saved for this company."); }
      catch (err) { setMessage(error(err)); } finally { setBusy(false); }
    }}><Save size={16} />{busy ? "Saving…" : "Save banner"}</button></div>
    {message && <p className="banner-message" role="status">{message}</p>}
  </section>;
}
