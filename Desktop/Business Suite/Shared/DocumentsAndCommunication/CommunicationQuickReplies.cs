using System.Text.Json;

namespace Business_Suite;

internal sealed record QuickReply(string Name, string Text, bool Favorite);
internal sealed record QuickReplies(List<QuickReply> Replies);

internal sealed class CommunicationQuickReplyStore
{
    private const int MaximumSize = 4 * 1024 * 1024;
    private readonly SalesIntentJournal<QuickReplies> file;

    internal CommunicationQuickReplyStore(DesktopDatabaseSettings settings)
    {
        file = new(settings, "Communication quick replies", settings.ExpectedAddress, Validate,
            "Saved quick replies could not be read.", MaximumSize);
    }

    internal QuickReplies Load()
    {
        using var held = file.Acquire();
        return file.Read() ?? Defaults();
    }

    internal QuickReplies Add(string name, string text) => Change(replies =>
    {
        var item = new QuickReply(name.Trim(), text.Trim(), false);
        if (replies.Any(reply => reply.Name == item.Name))
            throw new ArgumentException("A quick reply already uses that name.");
        replies.Add(item);
    });

    internal QuickReplies ToggleFavorite(string name) => Change(replies =>
    {
        int index = replies.FindIndex(reply => reply.Name == name);
        if (index < 0)
            throw new InvalidOperationException("This quick reply is no longer available.");
        replies[index] = replies[index] with { Favorite = !replies[index].Favorite };
    });

    private QuickReplies Change(Action<List<QuickReply>> action)
    {
        using var held = file.Acquire();
        var result = file.Read() ?? Defaults();
        action(result.Replies);
        Validate(result);
        if (JsonSerializer.SerializeToUtf8Bytes(result).Length > MaximumSize)
            throw new InvalidOperationException("The local quick reply library is full.");
        file.Save(result);
        return result;
    }

    private static void Validate(QuickReplies library)
    {
        if (library.Replies is null || library.Replies.Any(reply => reply is null ||
                string.IsNullOrWhiteSpace(reply.Name) || reply.Name.Length > 80 || reply.Name.Any(char.IsControl) ||
                string.IsNullOrWhiteSpace(reply.Text) || reply.Text.Length > 4096) ||
            library.Replies.Select(reply => reply.Name).Distinct(StringComparer.Ordinal).Count() != library.Replies.Count)
            throw new ArgumentException("Enter a reply name of up to 80 characters and text of up to 4,096 characters.");
    }

    private static QuickReplies Defaults() => new(new List<QuickReply>
    {
        new("Welcome", "Thank you for contacting us. How can we help you today?", true),
        new("Checking your request", "Thank you for the details. I am checking your request and will update you here.", false),
        new("Request details", "Could you share your order or service request reference so we can assist you?", false)
    });
}
