import * as Dropdown from "@radix-ui/react-dropdown-menu";
import { AlignJustify, Check } from "lucide-react";
import { useThemeStore } from "@/store/themeStore";
export default function DensityControl() {
  const { density, setDensity } = useThemeStore();
  return (
    <Dropdown.Root>
      <Dropdown.Trigger asChild>
        <button
          className="kf-density-control"
          aria-label="Display density"
          title="Display density"
        >
          <AlignJustify size={17} />
        </button>
      </Dropdown.Trigger>
      <Dropdown.Portal>
        <Dropdown.Content align="end" sideOffset={7} className="kf-select-menu">
          <Dropdown.Label className="px-2 py-1 text-xs text-muted-foreground">
            Display density
          </Dropdown.Label>
          {(["comfortable", "compact"] as const).map((value) => (
            <Dropdown.Item
              key={value}
              className="kf-select-item"
              onSelect={() => setDensity(value)}
            >
              {density === value && <Check size={14} />}
              <span className="capitalize">{value}</span>
            </Dropdown.Item>
          ))}
        </Dropdown.Content>
      </Dropdown.Portal>
    </Dropdown.Root>
  );
}
