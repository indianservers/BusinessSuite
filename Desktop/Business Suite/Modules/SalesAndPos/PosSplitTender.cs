namespace Business_Suite;

internal sealed record PosTenderPart(Guid Key, string Method, decimal Amount, string? Reference);
internal sealed record PosTenderAllocation(List<PosTenderPart> Payments, decimal Change)
{
    internal decimal Paid => Payments.Sum(part => part.Amount);
}

internal sealed partial class SalesOrderRepository
{
    internal static PosTenderAllocation AllocatePosSplitTender(decimal total, IReadOnlyList<PosTenderPart> parts, bool requiresFullPayment)
    {
        if (parts.Count is < 1 or > 10 ||
            parts.Any(part => part is null || part.Key == Guid.Empty || part.Amount <= 0 || part.Amount > 99999999999m ||
                decimal.Round(part.Amount, 2) != part.Amount ||
                part.Method is not ("cash" or "card" or "upi" or "bank_transfer" or "credit") ||
                (part.Method == "credit" && part.Reference is not null) ||
                part.Reference is { } reference && (reference.Length > 120 || reference.IndexOf('\0') >= 0)) ||
            parts.Select(part => part.Key).Distinct().Count() != parts.Count)
            throw new ArgumentException("Use one to ten valid payment entries with positive amounts and optional references up to 120 characters.");

        decimal nonCash = parts.Where(part => part.Method is not ("cash" or "credit")).Sum(part => part.Amount);
        decimal credit = parts.Where(part => part.Method == "credit").Sum(part => part.Amount);
        decimal cash = parts.Where(part => part.Method == "cash").Sum(part => part.Amount);
        if (requiresFullPayment && (credit > 0 || nonCash + cash < total))
            throw new ArgumentException("Walk-in sales require full payment at checkout. Select a named customer for credit.");
        decimal remaining = total - nonCash - credit;
        if (credit == total || remaining < 0 || cash < remaining || (credit > 0 && cash != remaining))
            throw new ArgumentException("Cover the bill with received payments and any explicit credit balance. Only cash may exceed the bill for change.");

        var payments = new List<PosTenderPart>();
        foreach (var part in parts)
        {
            if (part.Method == "credit")
                continue;
            if (part.Method != "cash")
            {
                payments.Add(part);
                continue;
            }
            decimal applied = Math.Min(part.Amount, remaining);
            if (applied > 0)
                payments.Add(part with { Amount = applied });
            remaining -= applied;
        }
        if (payments.Count == 0)
            throw new ArgumentException("Use a credit checkout when the entire invoice is unpaid.");
        return new PosTenderAllocation(payments, cash - payments.Where(part => part.Method == "cash").Sum(part => part.Amount));
    }

    private static PosTenderAllocation GetPosTenderAllocation(PosCheckoutIntent intent) => intent.PaymentMethod switch
    {
        "credit" => new PosTenderAllocation(new List<PosTenderPart>(), 0),
        "split" => AllocatePosSplitTender(intent.Total, intent.Parts ?? throw new ArgumentException("Enter split payments."),
            requiresFullPayment: intent.CustomerId == 0),
        _ => new PosTenderAllocation(new List<PosTenderPart> { new(intent.PaymentKey, intent.PaymentMethod, intent.Total, intent.Reference) }, 0)
    };
}
