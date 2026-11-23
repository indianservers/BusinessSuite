using Npgsql;

namespace Business_Suite;

public sealed partial class LeadReminderProcessingForm : Form
{
    private enum ReminderKind { FollowUp,FirstResponse,SalesProcess }
    private readonly CancellationTokenSource lifetime=new();

    public LeadReminderProcessingForm() => InitializeComponent();

    private void FormShown(object sender,EventArgs e)
    {
        try
        {
            var settings=DesktopDatabaseSettings.Load();
            scopeLabel.Text=settings.BranchId is int branch
                ?$"Company #{settings.OrganizationId} · Branch #{branch}"
                :$"Company #{settings.OrganizationId} · All branches";
            processButton.Enabled=true;
            slaButton.Enabled=true;
            salesButton.Enabled=true;
        }
        catch(Exception error) when(error is ArgumentException or InvalidOperationException or IOException or UnauthorizedAccessException)
        {
            feedback.Text=error.Message;
        }
    }

    private async void ProcessClicked(object sender,EventArgs e) => await ProcessAsync(ReminderKind.FollowUp);

    private async void SlaClicked(object sender,EventArgs e) => await ProcessAsync(ReminderKind.FirstResponse);

    private void RoutingClicked(object sender,EventArgs e)
    {
        using var form=new LeadRoutingForm();
        if (form.ShowDialog(this)==DialogResult.OK)
            feedback.Text="Lead routing settings saved.";
    }

    private void SetupClicked(object sender,EventArgs e)
    {
        using var form=new LeadSalesSetupForm();
        if (form.ShowDialog(this)==DialogResult.OK)
            feedback.Text="Sales process settings saved.";
    }

    private async void SalesClicked(object sender,EventArgs e) => await ProcessAsync(ReminderKind.SalesProcess);

    private async Task ProcessAsync(ReminderKind kind)
    {
        if (!processButton.Enabled)
            return;
        var cancellation=lifetime.Token;
        processButton.Enabled=slaButton.Enabled=salesButton.Enabled=false;
        feedback.Text="Checking Lead reminders…";
        try
        {
            string message;
            if (kind==ReminderKind.SalesProcess)
            {
                var result=await LeadStore.ProcessLeadSalesRemindersAsync(cancellation);
                message=result.Enabled
                    ?$"{result.Manager:N0} manager, {result.Proposal:N0} proposal and {result.Nurture:N0} nurture alerts added."
                    :"The company Lead sales process is disabled.";
            }
            else if (kind==ReminderKind.FirstResponse)
            {
                var result=await LeadStore.ProcessLeadSlaRemindersAsync(cancellation);
                message=$"{result.Leads:N0} {(result.Leads==1?"Lead":"Leads")} escalated. "+
                    $"{result.Notifications:N0} in-app alerts added. {result.Skipped:N0} leads had no eligible recipient.";
            }
            else
            {
                var result=await LeadStore.ProcessDueLeadRemindersAsync(cancellation);
                message=$"{result.Sent:N0} {(result.Sent==1?"reminder":"reminders")} added. "+
                    $"{result.Skipped:N0} of {result.Examined:N0} items had no eligible recipient.";
            }
            if (!cancellation.IsCancellationRequested)
                feedback.Text=message;
        }
        catch(OperationCanceledException) when(cancellation.IsCancellationRequested) { }
        catch(Exception error) when(error is NpgsqlException or IOException or InvalidOperationException or
            UnauthorizedAccessException or ArgumentException or TimeoutException)
        {
            if (!cancellation.IsCancellationRequested)
                feedback.Text=error is UnauthorizedAccessException or InvalidOperationException or ArgumentException
                    ?error.Message:"Could not process Lead reminders in PostgreSQL.";
        }
        finally
        {
            if (!cancellation.IsCancellationRequested)
                processButton.Enabled=slaButton.Enabled=salesButton.Enabled=true;
        }
    }

    private void FormIsClosed(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
}
