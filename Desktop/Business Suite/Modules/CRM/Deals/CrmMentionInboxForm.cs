using System.Data;
using Npgsql;

namespace Business_Suite;

public sealed partial class CrmMentionInboxForm : Form
{
    private readonly CrmDealRepository? repository;
    private readonly CancellationTokenSource lifetime=new();
    private bool busy;
    private bool ready;

    public CrmMentionInboxForm() => InitializeComponent();
    internal CrmMentionInboxForm(DesktopDatabaseSettings settings) : this() => repository=new(settings);

    private async void InboxShown(object sender,EventArgs e)
    {
        ready=true;
        await RunAsync(LoadAsync);
    }

    private async void RefreshClicked(object sender,EventArgs e) => await RunAsync(LoadAsync);
    private void SelectionChanged(object sender,EventArgs e) => UpdateActions();

    private async void OpenClicked(object sender,EventArgs e)
    {
        if (repository is null || Selected is not DataRowView row)
            return;
        int deal=(int)row["deal_id"];
        await RunAsync(async cancellation =>
        {
            var details=await repository.DetailAsync(deal,false,cancellation);
            if (cancellation.IsCancellationRequested)
                return;
            using var form=new CrmDealDetailForm(details,repository);
            if (row["event_type"] as string=="crm_mention")
                form.SelectNotes();
            form.ShowDialog(this);
            if (!cancellation.IsCancellationRequested)
                await LoadAsync(cancellation);
        });
    }

    private async void MarkReadClicked(object sender,EventArgs e)
    {
        if (repository is null || Selected is not DataRowView row)
            return;
        int id=(int)row["id"];
        await RunAsync(async cancellation =>
        {
            await repository.MarkMentionReadAsync(id,cancellation);
            await LoadAsync(cancellation);
        });
    }

    private async Task LoadAsync(CancellationToken cancellation)
    {
        if (repository is null)
            return;
        var data=await repository.MentionInboxAsync(unreadBox.Checked,cancellation);
        if (cancellation.IsCancellationRequested)
            return;
        grid.DataSource=data;
        status.Text=data.Rows.Count==0?"No matching Deal alerts.":$"{data.Rows.Count:N0} most recent matching Deal alerts.";
    }

    private async Task RunAsync(Func<CancellationToken,Task> operation)
    {
        if (!ready || busy || repository is null)
            return;
        var cancellation=lifetime.Token;
        busy=true;
        UpdateActions();
        status.Text="Loading Deal alerts…";
        try
        {
            await operation(cancellation);
        }
        catch(OperationCanceledException) when (cancellation.IsCancellationRequested) { }
        catch(Exception error) when(error is InvalidOperationException or UnauthorizedAccessException or
            ArgumentException or IOException or NpgsqlException or TimeoutException)
        {
            if (!cancellation.IsCancellationRequested)
            {
                if (error is UnauthorizedAccessException)
                    grid.DataSource=null;
                status.Text=error is InvalidOperationException or UnauthorizedAccessException?error.Message
                    :"Could not load Deal alerts. Check PostgreSQL and try again.";
            }
        }
        finally
        {
            busy=false;
            if (!cancellation.IsCancellationRequested)
                UpdateActions();
        }
    }

    private DataRowView? Selected=>grid.CurrentRow?.DataBoundItem as DataRowView;

    private void UpdateActions()
    {
        refreshButton.Enabled=unreadBox.Enabled=ready && !busy;
        var selected=Selected;
        openButton.Enabled=ready && !busy && selected is not null;
        readButton.Enabled=openButton.Enabled && selected!["is_read"] is false;
    }

    private void InboxClosed(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
}
