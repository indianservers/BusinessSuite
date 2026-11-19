import type {Plugin} from "vite";

/** Fetch only the current destination's built code before the app shell starts.
 * No module is executed and no data, forms or authority are prefetched. */
export function criticalRoutePreload(): Plugin {
  const destinations: Record<string,string> = {
    "/srm/appointments": "/src/apps/srm/industry/IndustryOperationsPage.tsx",
    "/srm/service-scheduling": "/src/shared/scheduling/ServiceSchedulingWorkspace.tsx",
    "/srm/pos/terminal": "/src/apps/srm/pages/SRMPOSPage.tsx",
    "/srm/pos": "/src/apps/srm/pages/SRMPOSPage.tsx",
    "/srm/inventory/products": "/src/shared/catalog/CatalogPage.tsx",
  };
  return {
    name: "critical-route-preload",
    apply: "build",
    transformIndexHtml: {order:"post", handler(_html, context) {
      if (!context.bundle) return;
      const bundle=context.bundle;
      const map: Record<string,string[]>={};
      for (const [route,source] of Object.entries(destinations)) {
        const entry=Object.values(bundle).find(chunk=>chunk.type==="chunk" && chunk.facadeModuleId?.replaceAll("\\","/").endsWith(source));
        if (!entry || entry.type!=="chunk") throw new Error(`Missing critical route chunk: ${source}`);
        const files=new Set<string>();
        const visit=(name:string)=>{
          if(files.has(name))return;
          const chunk=bundle[name];
          if(!chunk||chunk.type!=="chunk")return;
          files.add(name);
          chunk.imports.forEach(visit);
        };
        visit(entry.fileName);
        map[route]=[...files].map(name=>`/${name}`);
      }
      return [{tag:"script",attrs:{"data-critical-route-preload":""},injectTo:"head-prepend",children:`(()=>{const paths=${JSON.stringify(map)};for(const href of paths[location.pathname.replace(/\\/$/,"")]||[]){const link=document.createElement("link");link.rel="modulepreload";link.crossOrigin="";link.href=href;document.head.appendChild(link)}})();`}];
    }},
  };
}
