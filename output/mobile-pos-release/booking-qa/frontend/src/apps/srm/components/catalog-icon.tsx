import { Activity, Box, Car, FlaskConical, Shirt, HeartPulse, Leaf, Monitor, Pill, Scissors, ShoppingBag, Sparkles, Stethoscope, Tag, TestTube2, UserRound, Wrench, type LucideIcon } from 'lucide-react';

/** Semantic catalogue icons share the suite icon family across every pack. */
export function catalogIcon(name: string, category: string, service: boolean): LucideIcon {
  const value = `${name} ${category}`.toLowerCase();
  const rules: [RegExp, LucideIcon][] = [
    [/ecg|electrocardio/, Activity], [/cardio|heart/, HeartPulse], [/blood|laboratory/, TestTube2],
    [/diagnostic/, FlaskConical], [/medicine|tablet|capsule|pharma/, Pill], [/consultation|general medicine|doctor/, Stethoscope],
    [/hair styling|hair cut|haircut|alteration|tailor/, Scissors], [/spa|body therapy|skin/, Leaf],
    [/personal shopping/, ShoppingBag], [/apparel|shirt|fitting/, Shirt], [/electronic|headphone/, Monitor],
    [/accessor|wallet/, Tag], [/maintenance|oil change|alignment|repair/, Wrench], [/wash|detail/, Car],
    [/beauty|treatment/, Sparkles], [/consult|employee/, UserRound],
  ];
  return rules.find(([pattern]) => pattern.test(value))?.[1] || (service ? UserRound : Box);
}

