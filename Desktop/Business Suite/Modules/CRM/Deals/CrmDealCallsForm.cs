using System.Data;
using Npgsql;

namespace Business_Suite;

public sealed partial class CrmDealCallsForm : Form
{
    private readonly CrmDealRepository? repository;
    private readonly int deal;
    private readonly bool canWrite;
    private readonly CancellationTokenSource lifetime=new();
    private bool busy;
    private bool loaded;
    private (int Id,string Revision,DateTime OriginalUtc)? editing;

    public CrmDealCallsForm() => InitializeComponent();
    internal CrmDealCallsForm(CrmDealRepository repository,int deal,bool canWrite) : this()
    {
        this.repository=repository;
        this.deal=deal;
        this.canWrite=canWrite;
    }

    internal bool Changed {get;private set;}

    private async void FormShown(object sender,EventArgs e)
    {
        codeBox.Items.AddRange(CrmPhone.CallingCodes);
        codeBox.SelectedItem=CrmPhone.DefaultCallingCode;
        await RunAsync(false);
    }

    private async void SaveClicked(object sender,EventArgs e) => await RunAsync(true);

    private void CallSelected(object sender,EventArgs e) => UpdateActions();

    private void EditClicked(object sender,EventArgs e)
    {
        if (!editButton.Enabled || grid.CurrentRow?.DataBoundItem is not DataRowView row)
            return;
        DateTime original=DateTime.SpecifyKind((DateTime)row["occurred"],DateTimeKind.Utc);
        DateTime local=original.ToLocalTime();
        if (local<whenBox.MinDate || local>whenBox.MaxDate)
        {
            feedback.Text="This call time is outside the date picker's range.";
            return;
        }
        editing=((int)row["id"],(string)row["revision"],original);
        whenBox.Value=local;
        directionBox.SelectedItem=Convert.ToString(row["direction"]);
        string? code=row["phone_number_country_code"] as string;
        codeBox.SelectedItem=codeBox.Items.Contains(code)?code:CrmPhone.DefaultCallingCode;
        phoneBox.Text=Convert.ToString(row["phone_number"]);
        durationPresentBox.Checked=row["duration_seconds"] is int;
        durationBox.Value=row["duration_seconds"] is int seconds?Math.Max(seconds,0):0;
        outcomeBox.Text=Convert.ToString(row["outcome"]);
        notesBox.Text=Convert.ToString(row["notes"]);
        feedback.Text=$"Editing call #{editing.Value.Id}.";
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
        if (!archiveButton.Enabled || repository is null || grid.CurrentRow?.DataBoundItem is not DataRowView row)
            return;
        if (MessageBox.Show(this,"Archive the selected call?","Deal calls",MessageBoxButtons.YesNo,
            MessageBoxIcon.Question,MessageBoxDefaultButton.Button2)!=DialogResult.Yes)
            return;
        await RunAsync(false,async cancellation =>
        {
            await repository.ArchiveDealCallAsync(deal,(int)row["id"],(string)row["revision"],cancellation);
            Changed=true;
        });
    }

    private void FollowUpClicked(object sender,EventArgs e)
    {
        if (repository is null || !followUpButton.Enabled || grid.CurrentRow?.DataBoundItem is not DataRowView row)
            return;
        using var form=new CrmDealCallFollowUpForm(repository,deal,(int)row["id"],Convert.ToString(row["outcome"])??"");
        if (form.ShowDialog(this)==DialogResult.OK)
        {
            Changed|=form.TaskCreated;
            feedback.Text=form.ResultMessage;
        }
    }

    private async Task RunAsync(bool save,Func<CancellationToken,Task>? operation=null)
    {
        if (busy || repository is null || (save && !canWrite))
            return;
        busy=true;
        UpdateActions();
        var cancellation=lifetime.Token;
        try
        {
            if (save)
            {
                var clock=DateTime.SpecifyKind(whenBox.Value,DateTimeKind.Unspecified);
                if (TimeZoneInfo.Local.IsInvalidTime(clock))
                    throw new ArgumentException("The entered time does not exist in the local time zone.");
                DateTime utc=editing is { } original && original.OriginalUtc.ToLocalTime()==clock
                    ?original.OriginalUtc:TimeZoneInfo.ConvertTimeToUtc(clock,TimeZoneInfo.Local);
                var draft=new DealCallDraft(directionBox.Text,codeBox.Text,phoneBox.Text,utc,
                    durationPresentBox.Checked?(int)durationBox.Value:null,outcomeBox.Text,notesBox.Text);
                if (editing is { } current)
                    await repository.SaveDealCallAsync(deal,current.Id,current.Revision,draft,cancellation);
                else
                    await repository.AddDealCallAsync(deal,draft,cancellation);
                Changed=true;
                ResetEditor();
            }
            if (operation is not null)
                await operation(cancellation);
            var calls=await repository.DealCallsAsync(deal,cancellation);
            if (cancellation.IsCancellationRequested)
                return;
            grid.DataSource=calls;
            loaded=true;
            feedback.Text=save?"Call saved.":operation is not null?"Call archived.":calls.Rows.Count==0?"No calls recorded.":"";
        }
        catch(OperationCanceledException) when(cancellation.IsCancellationRequested) { }
        catch(Exception error) when(error is NpgsqlException or IOException or TimeoutException or
            ArgumentException or InvalidOperationException or UnauthorizedAccessException)
        {
            if (!cancellation.IsCancellationRequested)
                feedback.Text=error is ArgumentException or InvalidOperationException or UnauthorizedAccessException
                    ?error.Message:"Could not complete the call operation. Check PostgreSQL.";
        }
        finally
        {
            busy=false;
            if (!cancellation.IsCancellationRequested)
                UpdateActions();
        }
    }

    private void ResetEditor()
    {
        editing=null;
        directionBox.SelectedIndex=0;
        codeBox.SelectedItem=CrmPhone.DefaultCallingCode;
        phoneBox.Clear();
        durationBox.Value=0;
        durationPresentBox.Checked=false;
        outcomeBox.Clear();
        notesBox.Clear();
        whenBox.Value=DateTime.Now;
    }

    private void DurationChanged(object sender,EventArgs e) => UpdateActions();
    private void UpdateActions()
    {
        saveButton.Enabled=loaded&&canWrite&&!busy;
        saveButton.Text=editing.HasValue?"Save call":"Log call";
        followUpButton.Enabled=editButton.Enabled=archiveButton.Enabled=saveButton.Enabled&&!editing.HasValue&&
            grid.CurrentRow?.DataBoundItem is DataRowView;
        cancelEditButton.Enabled=editing.HasValue&&!busy;
        directionBox.Enabled=codeBox.Enabled=phoneBox.Enabled=whenBox.Enabled=durationPresentBox.Enabled=
            outcomeBox.Enabled=notesBox.Enabled=saveButton.Enabled;
        durationBox.Enabled=saveButton.Enabled&&durationPresentBox.Checked;
        closeButton.Enabled=!busy;
    }

    private void FormIsClosing(object sender,FormClosingEventArgs e) => e.Cancel=busy;
    private void FormIsClosed(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
}
