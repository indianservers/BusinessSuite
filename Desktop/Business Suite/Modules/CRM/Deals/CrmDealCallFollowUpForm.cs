using Npgsql;

namespace Business_Suite;

public sealed partial class CrmDealCallFollowUpForm : Form
{
    private readonly CrmDealRepository? repository;
    private readonly int deal;
    private readonly int source;
    private readonly bool meeting;
    private readonly CancellationTokenSource lifetime=new();
    private bool saving;

    public CrmDealCallFollowUpForm() => InitializeComponent();
    internal CrmDealCallFollowUpForm(CrmDealRepository repository,int deal,int source,string context,bool meeting=false) : this()
    {
        this.repository=repository;
        this.deal=deal;
        this.source=source;
        this.meeting=meeting;
        string suggestion="Follow up: "+(string.IsNullOrWhiteSpace(context)?(meeting?"Customer meeting":"Customer call"):context);
        titleBox.Text=suggestion.Length<=220?suggestion:suggestion.Substring(0,220);
    }

    internal bool TaskCreated {get;private set;}
    internal string ResultMessage {get;private set;}="";

    private async void SaveClicked(object sender,EventArgs e)
    {
        if (repository is null || saving)
            return;
        if (!dueBox.Checked)
        {
            feedback.Text="Choose when the follow-up is due.";
            return;
        }
        saving=true;
        saveButton.Enabled=cancelButton.Enabled=titleBox.Enabled=dueBox.Enabled=false;
        try
        {
            var value=dueBox.Value;
            var local=new DateTime(value.Year,value.Month,value.Day,value.Hour,value.Minute,0,DateTimeKind.Unspecified);
            if (TimeZoneInfo.Local.IsInvalidTime(local))
                throw new ArgumentException("The selected time does not exist in the local time zone.");
            var due=TimeZoneInfo.ConvertTimeToUtc(local,TimeZoneInfo.Local);
            var result=meeting?await repository.AddDealMeetingFollowUpAsync(deal,source,titleBox.Text,due,lifetime.Token)
                :await repository.AddDealCallFollowUpAsync(deal,source,titleBox.Text,due,lifetime.Token);
            TaskCreated=result.Created;
            ResultMessage=result.Created?$"Follow-up task #{result.Id} created."
                :result.Archived?$"Follow-up task #{result.Id} already exists in the archive.":$"Follow-up task #{result.Id} already exists.";
            saving=false;
            DialogResult=DialogResult.OK;
        }
        catch(Exception error) when(error is NpgsqlException or ArgumentException or InvalidOperationException or
            UnauthorizedAccessException or IOException or TimeoutException)
        {
            feedback.Text=error is ArgumentException or InvalidOperationException or UnauthorizedAccessException
                ?error.Message:"Could not save the follow-up. Your entries are retained.";
        }
        finally
        {
            saving=false;
            if (!IsDisposed)
                saveButton.Enabled=cancelButton.Enabled=titleBox.Enabled=dueBox.Enabled=true;
        }
    }

    private void FormIsClosing(object sender,FormClosingEventArgs e) => e.Cancel=saving;
    private void FormIsClosed(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
}
