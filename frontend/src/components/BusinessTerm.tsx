import { useBusinessTerms } from '@/hooks/use-business-terms';
import type { TermKey } from '@/lib/business-profile';

/** A built-in caption only. Stored names and customer-authored text stay untouched. */
export default function BusinessTerm({ name, plural = false }: { name: TermKey; plural?: boolean }) {
  const { term } = useBusinessTerms();
  return term(name, plural);
}
