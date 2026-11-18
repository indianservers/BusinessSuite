import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { getProductForContext } from "@/lib/products";

export function usePageTitle(title: string) {
  const location = useLocation();
  const product = getProductForContext(location.pathname);

  useEffect(() => {
    document.title = `${title} - ${product.name}`;
  }, [product.name, title]);
}
