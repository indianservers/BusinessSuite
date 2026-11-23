using Npgsql;

namespace Business_Suite;

public sealed partial class CommunicationDraftListForm : Form
{
    private readonly CommunicationDraftRepository? drafts;

    public CommunicationDraftListForm()
    {
        InitializeComponent();
    }

    internal CommunicationDraftListForm(CommunicationDraftRepository drafts) : this()
    {
        this.drafts = drafts;
    }

    private async void RefreshClicked(object sender, EventArgs e)
    {
        if (drafts is null || !refreshButton.Enabled)
            return;
        refreshButton.Enabled = false;
        draftGrid.DataSource = null;
        bodyBox.Text = "";
        statusLabel.Text = "Loading email drafts…";
        try
        {
            var rows = await drafts.ListAsync(searchBox.Text.Trim());
            if (!IsDisposed)
            {
                draftGrid.DataSource = rows;
                statusLabel.Text = rows.Count == 0 ? "No email drafts match the search."
                    : rows.Count == 200 ? "Showing the latest 200 matching drafts."
                    : $"{rows.Count} {(rows.Count == 1 ? "draft" : "drafts")}";
            }
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException or InvalidOperationException)
        {
            if (!IsDisposed)
                statusLabel.Text = error is UnauthorizedAccessException or InvalidOperationException ? error.Message
                    : "Could not load email drafts. Check database connectivity and access, then refresh.";
        }
        finally
        {
            if (!IsDisposed)
                refreshButton.Enabled = true;
        }
    }

    private void SelectionChanged(object sender, EventArgs e)
    {
        bodyBox.Text = (draftGrid.CurrentRow?.DataBoundItem as CommunicationDraftRow)?.Body ?? "";
    }
}
