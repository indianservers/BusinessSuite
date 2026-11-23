using Telerik.WinControls.UI;

namespace Business_Suite;

public sealed partial class CommunicationQuickRepliesForm : Form
{
    private readonly CommunicationQuickReplyStore? store;
    private QuickReplies? library;

    public CommunicationQuickRepliesForm() => InitializeComponent();

    internal CommunicationQuickRepliesForm(CommunicationQuickReplyStore store) : this() => this.store = store;

    internal string? InsertedText { get; private set; }
    private QuickReply? Selected => grid.CurrentRow?.DataBoundItem as QuickReply;

    private void ReplyWindowShown(object? sender, EventArgs e)
    {
        if (store is null)
            return;
        try
        {
            library = store.Load();
            BindReplies();
        }
        catch (Exception error) when (Expected(error)) { feedback.Text = Friendly(error); }
    }

    private void SearchChanged(object? sender, EventArgs e) => BindReplies();

    private void BindReplies(string? selected = null)
    {
        if (library is null)
            return;
        var filter = search.Text.Trim();
        var replies = library.Replies.Where(reply => $"{reply.Name} {reply.Text}"
                .IndexOf(filter, StringComparison.OrdinalIgnoreCase) >= 0)
            .OrderByDescending(reply => reply.Favorite).ToArray();
        grid.DataSource = replies;
        if (selected is not null)
            grid.CurrentRow = grid.Rows.OfType<GridViewDataRowInfo>()
                .FirstOrDefault(row => (row.DataBoundItem as QuickReply)?.Name == selected);
        feedback.Text = replies.Length == 0 ? "No replies match the search." : "";
        UpdateActions();
    }

    private void SelectionChanged(object? sender, EventArgs e) => UpdateActions();

    private void InputChanged(object? sender, EventArgs e) => UpdateActions();

    private void UpdateActions()
    {
        if (saveButton is null)
            return;
        var selected = Selected;
        preview.Text = selected?.Text ?? "";
        insertButton.Enabled = favoriteButton.Enabled = selected is not null;
        favoriteButton.Text = selected?.Favorite == true ? "Unfavorite" : "Favorite";
        saveButton.Enabled = library is not null && !string.IsNullOrWhiteSpace(nameBox.Text) &&
            !string.IsNullOrWhiteSpace(bodyBox.Text);
    }

    private void InsertClicked(object? sender, EventArgs e)
    {
        if (Selected is not { } selected)
            return;
        InsertedText = selected.Text;
        DialogResult = DialogResult.OK;
        Close();
    }

    private void FavoriteClicked(object? sender, EventArgs e)
    {
        if (store is null || Selected is not { } selected)
            return;
        try
        {
            library = store.ToggleFavorite(selected.Name);
            BindReplies(selected.Name);
        }
        catch (Exception error) when (Expected(error)) { feedback.Text = Friendly(error); }
    }

    private void SaveClicked(object? sender, EventArgs e)
    {
        if (store is null || !saveButton.Enabled)
            return;
        try
        {
            string name = nameBox.Text.Trim();
            library = store.Add(name, bodyBox.Text);
            nameBox.Clear();
            bodyBox.Clear();
            search.Clear();
            BindReplies(name);
            feedback.Text = "Quick reply saved.";
        }
        catch (Exception error) when (Expected(error)) { feedback.Text = Friendly(error); }
    }

    private static bool Expected(Exception error) => error is IOException or UnauthorizedAccessException
        or ArgumentException or InvalidOperationException;

    private static string Friendly(Exception error) => error is IOException or UnauthorizedAccessException
        ? "The local quick reply library is unavailable or locked by another window." : error.Message;
}
