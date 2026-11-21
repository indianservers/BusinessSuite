import { Minus, Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';

type Props = {
  product: { id: number; name: string; trackInventory: boolean; stock: number; checkoutSupported?: boolean };
  quantity: number;
  locked: boolean;
  onRemove: () => void;
  onAdd: () => void;
};

export default function POSCatalogueQuantity({ product, quantity, locked, onRemove, onAdd }: Props) {
  return (
    <div className="pos-catalogue-quantity flex shrink-0 items-center justify-end gap-1" role="group" aria-label={`${product.name} quantity`}>
      <Button type="button" variant="outline" size="icon" className="h-7 w-7" aria-label={`Remove one ${product.name} from cart`} disabled={locked || quantity <= 0} onClick={onRemove}>
        <Minus size={14} />
      </Button>
      <span className="min-w-4 text-center text-xs font-semibold" aria-live="polite">{quantity}</span>
      <Button type="button" variant="outline" size="icon" className="h-7 w-7" data-product-id={product.id} aria-label={`Add ${product.name} to cart`} disabled={locked || product.checkoutSupported === false || (product.trackInventory && quantity >= product.stock)} onClick={onAdd}>
        <Plus size={14} />
      </Button>
    </div>
  );
}
