using Npgsql;

namespace Business_Suite;

public sealed partial class LeadNurtureConsentForm : Form
{
    private readonly LeadKey? key;
    private readonly CancellationTokenSource lifetime=new();

    public LeadNurtureConsentForm() => InitializeComponent();

    internal LeadNurtureConsentForm(LeadKey key,string name,LeadNurtureConsent consent) : this()
    {
        this.key=key;
        heading.Text=name;
        allowedBox.Checked=consent.Allowed;
        evidenceBox.Text=consent.Evidence;
    }

    private async void SaveClicked(object sender,EventArgs e)
    {
        if (key is null || !saveButton.Enabled)
            return;
        var cancellation=lifetime.Token;
        saveButton.Enabled=allowedBox.Enabled=evidenceBox.Enabled=false;
        feedback.Text="";
        try
        {
            await LeadStore.SaveNurtureConsentAsync(key,new(allowedBox.Checked,evidenceBox.Text),cancellation);
            if (!cancellation.IsCancellationRequested)
                DialogResult=DialogResult.OK;
        }
        catch(OperationCanceledException) when(cancellation.IsCancellationRequested) { }
        catch(Exception error) when(error is NpgsqlException or IOException or InvalidOperationException or
            UnauthorizedAccessException or ArgumentException or TimeoutException)
        {
            if (!cancellation.IsCancellationRequested)
                feedback.Text=error is ArgumentException or UnauthorizedAccessException or InvalidOperationException
                    ?error.Message:"Could not save nurture permission to PostgreSQL.";
        }
        finally
        {
            if (!cancellation.IsCancellationRequested)
                saveButton.Enabled=allowedBox.Enabled=evidenceBox.Enabled=true;
        }
    }

    private void FormIsClosed(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
}
