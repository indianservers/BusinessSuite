import { useEffect, useState } from "react";
import { ArrowUp } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function BackToTop() {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const main = document.querySelector("main");
    const onScroll = () => setVisible((main?.scrollTop || 0) > 300);
    main?.addEventListener("scroll", onScroll);
    onScroll();
    return () => main?.removeEventListener("scroll", onScroll);
  }, []);
  if (!visible) return null;
  return (
    <Button
      aria-label="Back to top"
      title="Back to top"
      size="icon"
      className="fixed bottom-5 right-5 z-40 h-10 w-10 rounded-full shadow-lg"
      onClick={() => document.querySelector("main")?.scrollTo({ top: 0, behavior: "smooth" })}
    >
      <ArrowUp className="h-4 w-4" />
    </Button>
  );
}
