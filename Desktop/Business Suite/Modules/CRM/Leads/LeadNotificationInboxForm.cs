using System.Data;
using Npgsql;

namespace Business_Suite;

public sealed partial class LeadNotificationInboxForm : Form
{
    private readonly CancellationTokenSource lifetime=new();
    private bool busy;
    private bool ready;

    public LeadNotificationInboxForm() => InitializeComponent();

    private async void InboxShown(object sender,EventArgs e)
    {
        ready=true;
        await RunAsync(LoadAsync);
    }

    private async void RefreshClicked(object sender,EventArgs e) => await RunAsync(LoadAsync);
    private void SelectionChanged(object sender,EventArgs e) => UpdateActions();

    private void OpenClicked(object sender,EventArgs e)
    {
        if (!openButton.Enabled || Selected is not DataRowView row)
            return;
        using var form=new LeadHistoryForm((int)row["lead_id"],(bool)row["potential"],(string)row["lead_name"]);
        form.ShowDialog(this);
    }

    private async void MarkReadClicked(object sender,EventArgs e)
    {
        if (!readButton.Enabled || Selected is not DataRowView row)
            return;
        int id=(int)row["id"];
        await RunAsync(async cancellation =>
        {
            await LeadStore.MarkLeadNotificationReadAsync(id,cancellation);
            await LoadAsync(cancellation);
        });
    }

    private async Task LoadAsync(CancellationToken cancellation)
    {
        var data=await LeadStore.LeadNotificationInboxAsync(unreadBox.Checked,cancellation);
        if (cancellation.IsCancellationRequested)
            return;
        grid.DataSource=data;
        status.Text=data.Rows.Count==0?"No matching Lead notifications.":$"{data.Rows.Count:N0} most recent matching Lead notifications.";
    }

    private async Task RunAsync(Func<CancellationToken,Task> operation)
    {
        if (!ready || busy)
            return;
        var cancellation=lifetime.Token;
        busy=true;
        UpdateActions();
        status.Text="Loading Lead notifications…";
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
                    :"Could not load Lead notifications. Check PostgreSQL and try again.";
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
        openButton.Enabled=ready&&!busy&&selected?["can_open_history"] is true;
        readButton.Enabled=ready&&!busy&&selected?["is_read"] is false;
    }

    private void InboxClosed(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
}
