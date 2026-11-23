using Npgsql;

namespace Business_Suite;

public sealed partial class LeadActivityEntryForm : Form
{
    private readonly LeadKey? key;
    private readonly bool scheduling;
    private readonly LeadFollowUpDraft? existing;
    private readonly CancellationTokenSource lifetime=new();

    public LeadActivityEntryForm() => InitializeComponent();

    internal LeadActivityEntryForm(LeadKey key,bool scheduling=false,LeadFollowUpDraft? existing=null) : this()
    {
        this.key=key;
        this.scheduling=scheduling;
        this.existing=existing;
        kindBox.SelectedIndex=0;
        duePicker.Value=DateTime.UtcNow.AddDays(1);
        if (scheduling)
        {
            Text="Schedule Lead follow-up";
            kindLabel.Text="Follow-up type";
            outcomeLabel.Text="Title";
            outcomeBox.MaxLength=180;
            scheduleKindBox.SelectedIndex=0;
            scheduleKindBox.Visible=scheduleDueLabel.Visible=duePicker.Enabled=true;
            ownerLabel.Visible=ownerBox.Visible=true;
            kindBox.Visible=followUpBox.Visible=respondedBox.Visible=false;
            saveButton.Text="Schedule follow-up";
            if (existing is not null)
            {
                Text="Reschedule Lead follow-up";
                saveButton.Text="Reschedule";
                outcomeBox.Text=existing.Title;
                scheduleKindBox.SelectedIndex=existing.Kind switch { "call"=>1,"email"=>2,"meeting"=>3,_=>0 };
                if (existing.Due is DateTime due)
                    duePicker.Value=due;
                reasonLabel.Visible=reasonBox.Visible=true;
            }
        }
    }

    private void DueChanged(object sender,EventArgs e) => duePicker.Enabled=followUpBox.Checked;

    private async void FormShown(object sender,EventArgs e)
    {
        if (!scheduling || key is null)
            return;
        var cancellation=lifetime.Token;
        saveButton.Enabled=ownerBox.Enabled=false;
        feedback.Text="Loading teammates with access to this Lead…";
        try
        {
            var owners=await LeadStore.FollowUpOwnersAsync(key,existing?.Owner,cancellation);
            if (!cancellation.IsCancellationRequested)
            {
                ownerBox.DisplayMember=nameof(CrmLookup.Name);
                ownerBox.DataSource=owners.Choices;
                ownerBox.SelectedIndex=owners.Choices.FindIndex(choice=>choice.Id==owners.Preferred);
                ownerBox.Enabled=saveButton.Enabled=owners.Choices.Count>0;
                feedback.Text=owners.Choices.Count==0?"No eligible teammates can access this Lead.":
                    ownerBox.SelectedIndex<0?"Choose a teammate with access to this Lead.":"";
            }
        }
        catch(OperationCanceledException) when(cancellation.IsCancellationRequested) { }
        catch(Exception error) when(error is NpgsqlException or IOException or InvalidOperationException or
            UnauthorizedAccessException or ArgumentException or TimeoutException)
        {
            if (!cancellation.IsCancellationRequested)
                feedback.Text=error is InvalidOperationException or UnauthorizedAccessException or ArgumentException
                    ?error.Message:"Could not load eligible teammates.";
        }
    }

    private async void SaveClicked(object sender,EventArgs e)
    {
        if (key is null || !saveButton.Enabled || kindBox.SelectedIndex<0)
            return;
        int? owner=(ownerBox.SelectedItem?.DataBoundItem as CrmLookup)?.Id;
        if (scheduling && !owner.HasValue)
        {
            feedback.Text="Choose a teammate with access to this Lead.";
            return;
        }
        var chosen=duePicker.Value;
        DateTime? due=scheduling||followUpBox.Checked
            ?new DateTime(chosen.Year,chosen.Month,chosen.Day,chosen.Hour,chosen.Minute,0,DateTimeKind.Utc):null;
        var cancellation=lifetime.Token;
        saveButton.Enabled=scheduleKindBox.Enabled=kindBox.Enabled=outcomeBox.Enabled=followUpBox.Enabled=
            respondedBox.Enabled=duePicker.Enabled=reasonBox.Enabled=ownerBox.Enabled=false;
        feedback.Text="";
        try
        {
            if (scheduling && due is DateTime followUp)
                await LeadStore.ScheduleLeadFollowUpAsync(key,scheduleKindBox.Text.ToLowerInvariant(),outcomeBox.Text,
                    followUp,cancellation,existing,reasonBox.Text,owner);
            else
                await LeadStore.RecordLeadActivityAsync(key,kindBox.Text.ToLowerInvariant(),outcomeBox.Text,due,cancellation,
                    respondedBox.Checked);
            if (!cancellation.IsCancellationRequested)
                DialogResult=DialogResult.OK;
        }
        catch(OperationCanceledException) when(cancellation.IsCancellationRequested) { }
        catch(Exception error) when(error is NpgsqlException or IOException or InvalidOperationException or
            UnauthorizedAccessException or ArgumentException or TimeoutException)
        {
            if (!cancellation.IsCancellationRequested)
                feedback.Text=error is InvalidOperationException or UnauthorizedAccessException or ArgumentException
                    ?error.Message:"Could not save Lead activity to PostgreSQL.";
        }
        finally
        {
            if (!cancellation.IsCancellationRequested)
            {
                saveButton.Enabled=scheduleKindBox.Enabled=kindBox.Enabled=outcomeBox.Enabled=followUpBox.Enabled=
                    respondedBox.Enabled=reasonBox.Enabled=true;
                duePicker.Enabled=scheduling||followUpBox.Checked;
                ownerBox.Enabled=scheduling;
            }
        }
    }

    private void FormIsClosed(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
}
