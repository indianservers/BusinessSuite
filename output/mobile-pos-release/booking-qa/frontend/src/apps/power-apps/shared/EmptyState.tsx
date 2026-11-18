import type React from "react";
import { Layers3 } from "lucide-react";
export function Empty({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="pa-empty">
      <Layers3 size={27} />
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
