namespace Business_Suite;

internal sealed record DraftRecipientReference(int Id, string Kind);
internal sealed record CommunicationWorkingDraft(DraftRecipientReference? Recipient, string Email, string Subject,
    string Body, Dictionary<string, string> MergeValues)
{
    internal static void Validate(CommunicationWorkingDraft draft)
    {
        if (draft.Email is null || draft.Email.Length > 180 || draft.Subject is null || draft.Subject.Length > 240 ||
            draft.Body is null || draft.Body.Length > 50000 || draft.MergeValues is null ||
            draft.MergeValues.Any(pair => pair.Value is null) ||
            draft.MergeValues.Sum(pair => (long)pair.Key.Length + pair.Value.Length) > 100000 ||
            (draft.Recipient is { } recipient && (recipient.Id <= 0 || recipient.Kind is not ("lead" or "contact" or "company"))))
            throw new ArgumentException("The working draft exceeds the local storage limits or has an invalid recipient.");
    }
}
