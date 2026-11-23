namespace Business_Suite;

internal sealed record EmailTemplateFavorites(HashSet<int> Ids);

internal sealed class CommunicationTemplateFavorites
{
    private readonly SalesIntentJournal<EmailTemplateFavorites> file;

    internal CommunicationTemplateFavorites(DesktopDatabaseSettings settings)
    {
        file = new(settings, "Email template favorites", settings.ExpectedAddress, Validate,
            "Email template favorites could not be read.", 4 * 1024 * 1024);
    }

    internal EmailTemplateFavorites Load()
    {
        using var held = file.Acquire();
        return Read();
    }

    internal void Toggle(int id)
    {
        using var held = file.Acquire();
        var favorites = Read();
        if (!favorites.Ids.Remove(id))
            favorites.Ids.Add(id);
        Validate(favorites);
        file.Save(favorites);
    }

    private EmailTemplateFavorites Read() => file.Read() ?? new(new HashSet<int>());

    private static void Validate(EmailTemplateFavorites value)
    {
        if (value.Ids is null || value.Ids.Count > 100000 || value.Ids.Any(id => id <= 0))
            throw new ArgumentException("The local template favorites list contains invalid data or is full.");
    }
}
