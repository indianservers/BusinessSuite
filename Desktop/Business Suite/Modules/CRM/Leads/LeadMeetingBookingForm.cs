using Npgsql;

namespace Business_Suite;

public sealed partial class LeadMeetingBookingForm : Form
{
    private readonly LeadKey? key;
    private readonly CancellationTokenSource lifetime=new();

    public LeadMeetingBookingForm() => InitializeComponent();

    internal LeadMeetingBookingForm(LeadKey key) : this()
    {
        this.key=key;
        purposeBox.SelectedIndex=0;
        timePicker.Value=DateTime.UtcNow.AddDays(1);
    }

    private async void SaveClicked(object sender,EventArgs e)
    {
        if (key is null || !saveButton.Enabled || purposeBox.SelectedIndex<0)
            return;
        var chosen=timePicker.Value;
        DateTime start=new(chosen.Year,chosen.Month,chosen.Day,chosen.Hour,chosen.Minute,0,DateTimeKind.Utc);
        string purpose=purposeBox.SelectedIndex==0?"consultation":"demo";
        var cancellation=lifetime.Token;
        saveButton.Enabled=purposeBox.Enabled=timePicker.Enabled=false;
        feedback.Text="";
        try
        {
            await LeadStore.BookLeadMeetingAsync(key,purpose,start,cancellation);
            if (!cancellation.IsCancellationRequested)
                DialogResult=DialogResult.OK;
        }
        catch(OperationCanceledException) when(cancellation.IsCancellationRequested) { }
        catch(Exception error) when(error is NpgsqlException or IOException or InvalidOperationException or
            UnauthorizedAccessException or ArgumentException or TimeoutException)
        {
            if (!cancellation.IsCancellationRequested)
                feedback.Text=error is InvalidOperationException or UnauthorizedAccessException or ArgumentException
                    ?error.Message:"Could not book the meeting in PostgreSQL.";
        }
        finally
        {
            if (!cancellation.IsCancellationRequested)
                saveButton.Enabled=purposeBox.Enabled=timePicker.Enabled=true;
        }
    }

    private void FormIsClosed(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
}
