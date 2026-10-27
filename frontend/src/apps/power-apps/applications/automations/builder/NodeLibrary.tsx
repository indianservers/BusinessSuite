import { useMemo, useState } from "react";
import { ChevronDown, Plus, Search, X, Star } from "lucide-react";
import { NodeIcon } from "./NodeIcon";
import { categories, categoryColors, type NodeDefinition } from "./types";
const paletteAliases: Record<string, string> = {
  "Logic & Conditions": "Conditions",
  "Flow Control": "Routing",
  "Data Transformation": "Data",
  Connectors: "Webhooks",
};
const paletteCategory = (category: string) =>
  paletteAliases[category] || category;
export function NodeLibrary({
  catalog,
  onAdd,
  onClose,
  picker = false,
}: {
  catalog: NodeDefinition[];
  onAdd: (definition: NodeDefinition) => void;
  onClose: () => void;
  picker?: boolean;
}) {
  const [favorites, setFavorites] = useState<string[]>(() => {
    try {
      const value = JSON.parse(
        localStorage.getItem("power-studio-favorites") || "[]",
      );
      return Array.isArray(value)
        ? value.filter((v) => typeof v === "string")
        : [];
    } catch {
      return [];
    }
  });
  const [recent, setRecent] = useState<string[]>(() => {
    try {
      const value = JSON.parse(
        localStorage.getItem("power-studio-recent") || "[]",
      );
      return Array.isArray(value)
        ? value.filter((v) => typeof v === "string")
        : [];
    } catch {
      return [];
    }
  });
  const remember = (id: string) => {
    const next = [id, ...recent.filter((n) => n !== id)].slice(0, 12);
    setRecent(next);
    try {
      localStorage.setItem("power-studio-recent", JSON.stringify(next));
    } catch {
      /* Optional local preferences */
    }
  };
  const groups = useMemo(
    () => [
      ...new Set([
        ...categories.map(paletteCategory),
        ...catalog.map((node) => paletteCategory(node.category)),
      ]),
    ],
    [catalog],
  );
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All nodes");
  const items = useMemo(
    () =>
      catalog.filter(
        (n) =>
          (category === "All nodes" ||
            (category === "Favorites"
              ? favorites.includes(n.id)
              : category === "Recently used"
                ? recent.includes(n.id)
                : paletteCategory(n.category) === category)) &&
          `${n.name} ${n.description} ${n.category} ${paletteCategory(n.category)}`
            .toLowerCase()
            .includes(query.toLowerCase()),
      ),
    [catalog, category, query, favorites, recent],
  );
  return (
    <section
      className={`as-library ${picker ? "as-picker" : ""}`}
      aria-label={picker ? "Add a node" : "Node library"}
    >
      <header>
        <div>
          <p>BUILD YOUR WORKFLOW</p>
          <h2>{picker ? "What happens next?" : "Node library"}</h2>
        </div>
        <button
          aria-label={picker ? "Close node picker" : "Collapse node library"}
          onClick={onClose}
        >
          <X size={17} />
        </button>
      </header>
      <label className="as-library-search">
        <Search size={15} />
        <input
          autoFocus={picker}
          placeholder={`Search ${catalog.length} nodes...`}
          aria-label="Search node library"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </label>
      <label className="as-category-select">
        <select
          aria-label="Node category"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        >
          <option>All nodes</option>
          <option>Favorites</option>
          <option>Recently used</option>
          {groups.map((c) => (
            <option key={c}>{c}</option>
          ))}
        </select>
        <ChevronDown size={14} />
      </label>
      <p className="as-library-count">{items.length} editor-ready nodes</p>
      <div className="as-library-scroll">
        {(category === "All nodes" ? groups : [category]).map((group) => {
          const rows = items.filter(
            (n) =>
              group === "Favorites" ||
              group === "Recently used" ||
              paletteCategory(n.category) === group,
          );
          return rows.length ? (
            <div className="as-library-group" key={group}>
              <h3>
                {group}
                <span>{rows.length}</span>
              </h3>
              {rows.map((def) => (
                <div className="as-palette-row" key={def.id}>
                  <button
                    aria-label={`${favorites.includes(def.id) ? "Unfavorite" : "Favorite"} ${def.name}`}
                    aria-pressed={favorites.includes(def.id)}
                    className="as-favorite"
                    onClick={() => {
                      const next = favorites.includes(def.id)
                        ? favorites.filter((id) => id !== def.id)
                        : [...favorites, def.id];
                      setFavorites(next);
                      try {
                        localStorage.setItem(
                          "power-studio-favorites",
                          JSON.stringify(next),
                        );
                      } catch {
                        /* Optional preference */
                      }
                    }}
                  >
                    <Star
                      size={12}
                      fill={
                        favorites.includes(def.id) ? "currentColor" : "none"
                      }
                    />
                  </button>
                  <button
                    key={def.id}
                    className="as-library-node"
                    aria-label={`Add ${def.name}`}
                    draggable
                    onDragStart={(event) => {
                      event.dataTransfer.setData(
                        "application/power-apps-node",
                        def.id,
                      );
                      event.dataTransfer.effectAllowed = "copy";
                      remember(def.id);
                    }}
                    onClick={() => {
                      remember(def.id);
                      onAdd(def);
                    }}
                  >
                    <span
                      style={{
                        background: `${categoryColors[def.category] || "#8254d0"}15`,
                        color: categoryColors[def.category] || "#8254d0",
                      }}
                    >
                      <NodeIcon name={def.icon} size={18} />
                    </span>
                    <span>
                      <strong>{def.name}</strong>
                      <small>{def.description}</small>
                      <small className="as-palette-capability">
                        {def.fields.filter((f) => f.required).length} inputs to
                        configure ·{" "}
                        {def.preview_supported
                          ? "Local preview"
                          : def.executable
                            ? "Runtime executor"
                            : "Runtime unavailable"}
                      </small>
                    </span>
                    <Plus size={13} />
                  </button>
                </div>
              ))}
            </div>
          ) : null;
        })}
        {!items.length && (
          <p className="as-library-empty">
            No matching nodes. Try another search.
          </p>
        )}
      </div>
      <footer>
        Local previews do not call providers.
        <br />
        Configure accounts, then publish and run supported nodes.
      </footer>
    </section>
  );
}
