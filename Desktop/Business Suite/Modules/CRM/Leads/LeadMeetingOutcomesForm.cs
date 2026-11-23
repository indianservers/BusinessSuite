using System.Data;
using Npgsql;

namespace Business_Suite;

public sealed partial class LeadMeetingOutcomesForm : Form
{
    private readonly LeadKey? key;
    private readonly CancellationTokenSource lifetime=new();
    private bool busy;

    public LeadMeetingOutcomesForm() => InitializeComponent();

    internal LeadMeetingOutcomesForm(LeadKey key,string name) : this()
    {
        this.key=key;
        heading.Text=name;
        replacementPicker.Value=DateTime.UtcNow.AddDays(1);
    }

    internal string SuccessMessage {get;private set;}="";

    private void BookClicked(object sender,EventArgs e)
    {
        if (key is null || busy)
            return;
        using var booking=new LeadMeetingBookingForm(key);
        if (booking.ShowDialog(this)==DialogResult.OK)
        {
            SuccessMessage="Lead meeting booked.";
            DialogResult=DialogResult.OK;
        }
    }

    private DataRowView? Selected => meetingsGrid.CurrentRow?.DataBoundItem as DataRowView;

    private async void RefreshClicked(object sender,EventArgs e) => await ReloadAsync();

    private async Task ReloadAsync()
    {
        if (key is null || busy)
            return;
        var cancellation=lifetime.Token;
        busy=true;
        UpdateActions(this,EventArgs.Empty);
        feedback.Text="Loading meetings…";
        try
        {
            var rows=await LeadStore.LeadMeetingsAsync(key.Id,cancellation);
            if (cancellation.IsCancellationRequested)
                return;
            meetingsGrid.DataSource=rows;
            feedback.Text=rows.Rows.Count==0?"No meetings recorded for this Lead.":"Select a meeting to update its outcome.";
        }
        catch(OperationCanceledException) when(cancellation.IsCancellationRequested) { }
        catch(Exception error) when(Expected(error))
        {
            if (!cancellation.IsCancellationRequested)
            {
                meetingsGrid.DataSource=null;
                feedback.Text=Message(error);
            }
        }
        finally
        {
            busy=false;
            if (!cancellation.IsCancellationRequested)
                UpdateActions(this,EventArgs.Empty);
        }
    }

    private void SelectionChanged(object sender,EventArgs e)
    {
        outcomeBox.Text=Selected?["outcome"] as string??"";
        if (!busy && Selected is not null)
            feedback.Text="Select a meeting to update its outcome.";
        UpdateActions(sender,e);
    }

    private void UpdateActions(object sender,EventArgs e)
    {
        var row=Selected;
        string? status=row?["status"] as string;
        bool external=row?["external_calendar"] is true;
        bool editable=!busy&&!external&&status is ("Scheduled" or "Confirmed");
        refreshButton.Enabled=meetingsGrid.Enabled=bookButton.Enabled=!busy;
        outcomeBox.Enabled=actionBox.Enabled=editable;
        replacementPicker.Enabled=editable&&actionBox.Text=="Rescheduled";
        saveButton.Enabled=editable&&actionBox.SelectedIndex>=0&&actionBox.Text!=status;
        if (!busy&&external)
            feedback.Text="This meeting is linked to an external calendar.";
    }

    private async void SaveClicked(object sender,EventArgs e)
    {
        if (key is null || !saveButton.Enabled || Selected is not DataRowView row)
            return;
        var cancellation=lifetime.Token;
        string action=actionBox.Text;
        DateTime selected=replacementPicker.Value;
        DateTime? replacement=action=="Rescheduled"
            ?new DateTime(selected.Year,selected.Month,selected.Day,selected.Hour,selected.Minute,0,DateTimeKind.Utc):null;
        busy=true;
        UpdateActions(this,EventArgs.Empty);
        bool saved=false;
        try
        {
            await LeadStore.SaveLeadMeetingOutcomeAsync(key,(int)row["id"],(string)row["revision"],action,outcomeBox.Text,
                cancellation,replacement);
            saved=true;
        }
        catch(OperationCanceledException) when(cancellation.IsCancellationRequested) { }
        catch(Exception error) when(Expected(error))
        {
            if (!cancellation.IsCancellationRequested)
                feedback.Text=Message(error);
        }
        finally
        {
            busy=false;
            if (!cancellation.IsCancellationRequested)
                UpdateActions(this,EventArgs.Empty);
        }
        if (saved&&!cancellation.IsCancellationRequested)
        {
            if (replacement.HasValue || action=="Attended")
            {
                SuccessMessage=replacement.HasValue?"Meeting rescheduled. Lead follow-up updated.":"Meeting attendance recorded.";
                DialogResult=DialogResult.OK;
            }
            else
                await ReloadAsync();
        }
    }

    private static bool Expected(Exception error) => error is NpgsqlException or IOException or InvalidOperationException or
        UnauthorizedAccessException or ArgumentException or TimeoutException;

    private static string Message(Exception error) => error is InvalidOperationException or UnauthorizedAccessException or ArgumentException
        ?error.Message:"Could not update meeting outcomes in PostgreSQL.";

    private void FormIsClosed(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
}
