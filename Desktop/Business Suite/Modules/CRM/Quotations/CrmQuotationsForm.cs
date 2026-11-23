using System.Data;
using Npgsql;

namespace Business_Suite;

public sealed partial class CrmQuotationsForm : Form
{
    private readonly QuoteDraftRepository? repository;
    private readonly CancellationTokenSource lifetime=new();
    private bool busy,canCreate,canEdit;
    public CrmQuotationsForm() => InitializeComponent();
    internal CrmQuotationsForm(DesktopDatabaseSettings settings) : this() => repository=new(settings);

    private DataRowView? Selected=>quotesGrid.CurrentRow?.DataBoundItem as DataRowView;
    private async void WorkspaceShown(object sender,EventArgs e)=>await ReloadAsync();
    private async void RefreshClicked(object sender,EventArgs e)=>await ReloadAsync();
    private void SelectionChanged(object sender,EventArgs e)=>UpdateActions();
    private async void NewClicked(object sender,EventArgs e)=>await OpenEditorAsync(null);
    private async void EditClicked(object sender,EventArgs e)
    {
        if (editButton.Enabled && Selected is DataRowView row)
            await OpenEditorAsync((int)row["id"]);
    }

    private async void ReviewClicked(object sender,EventArgs e)
    {
        if (repository is null||busy||Selected is not DataRowView row)
            return;
        using var review=new CrmQuoteLifecycleForm(repository,(int)row["id"]);
        if (review.ShowDialog(this)==DialogResult.OK)
        {
            await ReloadAsync();
            if (review.WasIssued && !IsDisposed)
                feedback.Text="Quotation PDF issued and retained. No provider delivery was recorded.";
        }
    }

    private async Task OpenEditorAsync(int? id)
    {
        if (repository is null || busy || (id.HasValue?!canEdit:!canCreate))
            return;
        using var editor=new CrmQuoteDraftForm(repository,id);
        if (editor.ShowDialog(this)==DialogResult.OK)
            await ReloadAsync();
    }

    private async Task ReloadAsync()
    {
        if (repository is null||busy)
            return;
        busy=true;
        UpdateActions();
        var token=lifetime.Token;
        feedback.Text="Loading quotations…";
        try
        {
            var result=await repository.ListAsync(searchBox.Text.Trim(),token);
            if (token.IsCancellationRequested) return;
            canCreate=result.CanCreate;
            canEdit=result.CanEdit;
            quotesGrid.DataSource=result.Rows;
            feedback.Text=result.Rows.Rows.Count==0?"No matching quotations.":$"{result.Rows.Rows.Count:N0} quotations";
        }
        catch(OperationCanceledException) when(token.IsCancellationRequested) { }
        catch(Exception error) when(Expected(error))
        {
            if (token.IsCancellationRequested) return;
            canCreate=canEdit=false;
            quotesGrid.DataSource=null;
            feedback.Text=Describe(error);
        }
        finally
        {
            busy=false;
            if (!token.IsCancellationRequested) UpdateActions();
        }
    }
    private void UpdateActions()
    {
        refreshButton.Enabled=searchBox.Enabled=!busy;
        newButton.Enabled=!busy&&canCreate;
        reviewButton.Enabled=!busy&&Selected is not null;
        editButton.Enabled=!busy&&canEdit&&Selected is DataRowView row&&
            Convert.ToString(row["status"])?.ToLowerInvariant() is "draft" or "rejected";
    }
    private void WorkspaceClosed(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
    internal static bool Expected(Exception error)=>error is InvalidOperationException or ArgumentException or UnauthorizedAccessException
        or NpgsqlException or IOException or TimeoutException or OverflowException;
    internal static string Describe(Exception error)=>error is InvalidOperationException or ArgumentException or UnauthorizedAccessException
        ?error.Message:"Could not load or save the quotation. Check the values and PostgreSQL connection.";
}
