using System.Data;
using Npgsql;

namespace Business_Suite;

public sealed partial class CrmDealMeetingsForm : Form
{
    private readonly CrmDealRepository? repository;
    private readonly int deal;
    private readonly bool canWrite;
    private readonly CancellationTokenSource lifetime=new();
    private bool loaded;
    private bool saving;
    private (int Id,string Revision,DateTime Start,DateTime End)? editing;

    public CrmDealMeetingsForm() => InitializeComponent();
    internal CrmDealMeetingsForm(CrmDealRepository repository,int deal,bool canWrite) : this()
    {
        this.repository=repository;
        this.deal=deal;
        this.canWrite=canWrite;
    }

    internal bool Changed {get;private set;}

    private async void FormShown(object sender,EventArgs e)
    {
        var now=DateTime.Now;
        startBox.Value=now;
        endBox.Value=now.AddMinutes(30);
        await RunAsync(false);
    }

    private async void SaveClicked(object sender,EventArgs e) => await RunAsync(true);

    private void SelectionChanged(object sender,EventArgs e) => UpdateActions();

    private void FollowUpClicked(object sender,EventArgs e)
    {
        if (repository is null || !followUpButton.Enabled || grid.CurrentRow?.DataBoundItem is not DataRowView row)
            return;
        using var form=new CrmDealCallFollowUpForm(repository,deal,(int)row["id"],Convert.ToString(row["title"])??"",meeting:true);
        if (form.ShowDialog(this)==DialogResult.OK)
        {
            Changed|=form.TaskCreated;
            feedback.Text=form.ResultMessage;
        }
    }

    private void EditClicked(object sender,EventArgs e)
    {
        if (!editButton.Enabled || grid.CurrentRow?.DataBoundItem is not DataRowView row)
            return;
        DateTime start=DateTime.SpecifyKind((DateTime)row["starts"],DateTimeKind.Utc);
        DateTime end=DateTime.SpecifyKind((DateTime)row["ends"],DateTimeKind.Utc);
        if (start.ToLocalTime()<startBox.MinDate || start.ToLocalTime()>startBox.MaxDate ||
            end.ToLocalTime()<endBox.MinDate || end.ToLocalTime()>endBox.MaxDate)
        {
            feedback.Text="This meeting time is outside the date picker's range.";
            return;
        }
        editing=((int)row["id"],(string)row["revision"],start,end);
        startBox.Value=start.ToLocalTime();
        endBox.Value=end.ToLocalTime();
        titleBox.Text=Convert.ToString(row["title"]);
        locationBox.Text=Convert.ToString(row["location"]);
        descriptionBox.Text=Convert.ToString(row["description"]);
        outcomeBox.Text=Convert.ToString(row["outcome"]);
        statusBox.SelectedItem=Convert.ToString(row["status"]);
        feedback.Text=$"Editing meeting #{editing.Value.Id}.";
        UpdateActions();
    }

    private void CancelEditClicked(object sender,EventArgs e)
    {
        ResetEditor();
        feedback.Text="";
        UpdateActions();
    }

    private async void ArchiveClicked(object sender,EventArgs e)
    {
        if (repository is null || !archiveButton.Enabled || grid.CurrentRow?.DataBoundItem is not DataRowView row ||
            MessageBox.Show(this,"Archive the selected meeting?","Deal meetings",MessageBoxButtons.YesNo,
                MessageBoxIcon.Question,MessageBoxDefaultButton.Button2)!=DialogResult.Yes)
            return;
        await RunAsync(false,async cancellation =>
        {
            await repository.ArchiveDealMeetingAsync(deal,(int)row["id"],(string)row["revision"],cancellation);
            Changed=true;
        });
    }

    private async Task RunAsync(bool save,Func<CancellationToken,Task>? operation=null)
    {
        if (repository is null || saving || (save && (!loaded || !canWrite)))
            return;
        saving=true;
        UpdateActions();
        var cancellation=lifetime.Token;
        try
        {
            if (save)
            {
                var draft=new DealMeetingDraft(titleBox.Text,descriptionBox.Text,locationBox.Text,
                    Utc(startBox.Value,editing?.Start),Utc(endBox.Value,editing?.End),statusBox.Text,outcomeBox.Text);
                if (editing is { } current)
                    await repository.SaveDealMeetingAsync(deal,current.Id,current.Revision,draft,cancellation);
                else
                    await repository.AddDealMeetingAsync(deal,draft,cancellation);
                Changed=true;
                ResetEditor();
            }
            if (operation is not null)
                await operation(cancellation);
            var meetings=await repository.DealMeetingsAsync(deal,cancellation);
            if (cancellation.IsCancellationRequested)
                return;
            grid.DataSource=meetings;
            loaded=true;
            feedback.Text=save?"Meeting saved locally. Calendar sync is unavailable in the desktop app."
                :operation is not null?"Meeting archived.":meetings.Rows.Count==0?"No meetings for this deal.":"";
        }
        catch(OperationCanceledException) when(cancellation.IsCancellationRequested) { }
        catch(Exception error) when(error is NpgsqlException or InvalidOperationException or ArgumentException
            or UnauthorizedAccessException or IOException or TimeoutException)
        {
            if (!cancellation.IsCancellationRequested)
                feedback.Text=error is ArgumentException or InvalidOperationException or UnauthorizedAccessException
                    ?error.Message:"Could not complete the meeting operation. Check PostgreSQL.";
        }
        finally
        {
            saving=false;
            if (!cancellation.IsCancellationRequested)
                UpdateActions();
        }
    }

    private void ResetEditor()
    {
        editing=null;
        titleBox.Clear();
        descriptionBox.Clear();
        locationBox.Clear();
        outcomeBox.Clear();
        statusBox.SelectedIndex=0;
        var now=DateTime.Now;
        startBox.Value=now;
        endBox.Value=now.AddMinutes(30);
    }

    private void UpdateActions()
    {
        saveButton.Text=editing.HasValue?"Save changes":"Save meeting";
        saveButton.Enabled=titleBox.Enabled=descriptionBox.Enabled=locationBox.Enabled=startBox.Enabled=endBox.Enabled=loaded&&canWrite&&!saving;
        statusBox.Enabled=outcomeBox.Enabled=saveButton.Enabled&&editing.HasValue;
        editButton.Enabled=archiveButton.Enabled=saveButton.Enabled&&!editing.HasValue&&grid.CurrentRow?.DataBoundItem is DataRowView row
            && row["external_calendar"] is false && (row["sync_status"] as string ?? "not_synced") is "" or "not_synced";
        followUpButton.Enabled=saveButton.Enabled&&!editing.HasValue&&grid.CurrentRow?.DataBoundItem is DataRowView;
        cancelEditButton.Enabled=saveButton.Enabled&&editing.HasValue;
        closeButton.Enabled=!saving;
    }

    private static DateTime Utc(DateTime value,DateTime? original)
    {
        if (original.HasValue && value==original.Value.ToLocalTime())
            return original.Value;
        var local=new DateTime(value.Year,value.Month,value.Day,value.Hour,value.Minute,0,DateTimeKind.Unspecified);
        if (TimeZoneInfo.Local.IsInvalidTime(local))
            throw new ArgumentException("A selected time does not exist in the local time zone.");
        return TimeZoneInfo.ConvertTimeToUtc(local,TimeZoneInfo.Local);
    }

    private void FormIsClosing(object sender,FormClosingEventArgs e) => e.Cancel=saving;
    private void FormIsClosed(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
}
