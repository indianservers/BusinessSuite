import {
  createElement,
  lazy,
  type ComponentType,
  type ComponentProps,
} from "react";
const failedImports = new Set<() => void>();
export function retryRouteImports() {
  for (const reset of [...failedImports]) reset();
}
/** Share intent imports with rendering. Only an explicit retry resets a rejected chunk. */
export function lazyRoute<T extends ComponentType<any>>(
  loader: () => Promise<{ default: T }>,
) {
  let pending: Promise<{ default: T }> | undefined, loaded: T | undefined;
  const reset = () => {
    pending = undefined;
    chunk = lazy(preload);
    failedImports.delete(reset);
  };
  const preload = () => {
    if (!pending)
      pending = loader()
        .then((module) => {
          loaded = module.default;
          failedImports.delete(reset);
          return module;
        })
        .catch((error) => {
          failedImports.add(reset);
          throw error;
        });
    return pending;
  };
  let chunk = lazy(preload);
  function PreloadableRoute(props: ComponentProps<T>) {
    return createElement(loaded || chunk, props);
  }
  return Object.assign(PreloadableRoute, { preload });
}
