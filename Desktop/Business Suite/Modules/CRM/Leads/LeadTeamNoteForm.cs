using Npgsql;

namespace Business_Suite;

public sealed partial class LeadTeamNoteForm : Form
{
    private readonly LeadKey? key;
    private readonly CancellationTokenSource lifetime=new();
    private bool busy;

    public LeadTeamNoteForm() => InitializeComponent();
    internal LeadTeamNoteForm(LeadKey key) : this() => this.key=key;

    private async void FormShown(object sender,EventArgs e)
    {
        if (key is null)
            return;
        var cancellation=lifetime.Token;
        feedback.Text="Loading eligible teammates…";
        try
        {
            var recipients=await LeadStore.TeamNoteRecipientsAsync(key,cancellation);
            if (cancellation.IsCancellationRequested)
                return;
            recipientsBox.DisplayMember=nameof(CrmLookup.Name);
            recipientsBox.Items.AddRange(recipients.Cast<object>().ToArray());
            recipientsBox.Enabled=recipients.Count>0;
            feedback.Text=recipients.Count==0?"No eligible mention recipients. You can still post an update.":"";
        }
        catch(OperationCanceledException) when(cancellation.IsCancellationRequested) { }
        catch(Exception error) when(Expected(error))
        {
            if (!cancellation.IsCancellationRequested)
                feedback.Text=Message(error,"Could not load eligible teammates.");
        }
        finally
        {
            if (!cancellation.IsCancellationRequested)
                saveButton.Enabled=true;
        }
    }

    private async void SaveClicked(object sender,EventArgs e)
    {
        if (key is null || busy || !saveButton.Enabled)
            return;
        var cancellation=lifetime.Token;
        int[] recipients=recipientsBox.CheckedItems.OfType<CrmLookup>().Where(x=>x.Id.HasValue)
            .Select(x=>x.Id!.Value).ToArray();
        busy=true;
        saveButton.Enabled=bodyBox.Enabled=recipientsBox.Enabled=false;
        feedback.Text="";
        try
        {
            await LeadStore.AddTeamNoteAsync(key,bodyBox.Text,recipients,cancellation);
            if (!cancellation.IsCancellationRequested)
                DialogResult=DialogResult.OK;
        }
        catch(OperationCanceledException) when(cancellation.IsCancellationRequested) { }
        catch(Exception error) when(Expected(error))
        {
            if (!cancellation.IsCancellationRequested)
                feedback.Text=Message(error,"Could not save the team update to PostgreSQL.");
        }
        finally
        {
            busy=false;
            if (!cancellation.IsCancellationRequested)
            {
                saveButton.Enabled=bodyBox.Enabled=true;
                recipientsBox.Enabled=recipientsBox.Items.Count>0;
            }
        }
    }

    private static bool Expected(Exception error) => error is NpgsqlException or IOException or InvalidOperationException or
        UnauthorizedAccessException or ArgumentException or TimeoutException;

    private static string Message(Exception error,string fallback) =>
        error is UnauthorizedAccessException or InvalidOperationException or ArgumentException?error.Message:fallback;

    private void FormIsClosed(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
}
