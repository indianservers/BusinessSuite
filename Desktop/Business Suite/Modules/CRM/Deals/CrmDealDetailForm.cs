using System.Data;
using System.Globalization;
using Npgsql;

namespace Business_Suite;

public sealed partial class CrmDealDetailForm : Form
{
    private readonly CrmDealRepository? repository;
    private readonly int id;
    private readonly CancellationTokenSource lifetime=new();
    private bool relatedChanged;
    private bool notesWritable;
    private bool notesBusy;
    private readonly bool canWriteTasks;

    public CrmDealDetailForm() => InitializeComponent();

    protected override void OnFormClosed(FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
        base.OnFormClosed(e);
    }

    internal CrmDealDetailForm(CrmDealDetails details,CrmDealRepository repository) : this()
    {
        this.repository=repository;
        DataRow record=details.Overview;
        id=(int)record["id"];
        editButton.Visible=closeDealButton.Visible=details.CanEdit;
        editStakeholdersButton.Visible=details.CanEditStakeholders;
        tasksButton.Visible=details.CanReadTasks;
        callsButton.Visible=details.CanReadTasks;
        meetingsButton.Visible=details.CanReadTasks;
        canWriteTasks=details.CanWriteTasks;
        heading.Text=Display("name");
        CrmDealHealth health=details.Health;
        string healthReasons=health.Reasons.Length==0?"":Environment.NewLine+string.Join(Environment.NewLine,health.Reasons);
        detailsBox.Text=string.Join(Environment.NewLine,new[]
        {
            $"Company: {Display("company")}",
            $"Primary contact: {Display("primary_contact")}",
            $"Pipeline: {Display("pipeline")}",
            $"Stage: {Display("stage")}",
            $"Status: {Display("status")}",
            $"Health: {health.Score}/100 · {health.Level}",
            $"Priority: {Display("priority")}",
            $"Deal type: {Display("deal_type")}",
            $"Source: {Display("source")}",
            $"Value: {Currency("amount")}",
            $"Expected revenue: {Currency("expected_revenue")}",
            $"Probability: {(record["probability"] is int probability ? $"{probability}%" : "—")}",
            $"Expected close: {Date("expected_close_date","dd MMM yyyy")}",
            $"Next action: {Date("next_follow_up_at","dd MMM yyyy HH:mm")}",
            $"Tags: {Display("tags_text")}",
            "",
            Display("description"),
            "",
            $"Deal age: {health.DealAge} days · Current stage: {health.StageAge} days",
            $"Days since last activity: {(health.ActivityGap?.ToString(CultureInfo.CurrentCulture)??"—")}"+healthReasons
        });
        peopleGrid.DataSource=details.Stakeholders;
        historyGrid.DataSource=details.History;
        peopleStatus.Text=details.Stakeholders.Rows.Count==0?"No visible stakeholders.":"";
        historyStatus.Text=details.History.Rows.Count==0?"No recorded deal history.":"";
        if (details.CanReadNotes)
            BindNotes(details);
        else
            detailTabs.TabPages.Remove(notesTab);

        string Display(string field) => Convert.ToString(record[field],CultureInfo.CurrentCulture) is string value &&
            !string.IsNullOrWhiteSpace(value)?value:"—";
        string Currency(string field) => record[field] is decimal amount?$"{Display("currency")} {amount:N2}":"—";
        string Date(string field,string format) => record[field] is DateTime value
            ? (value.Kind==DateTimeKind.Utc?value.ToLocalTime():value).ToString(format,CultureInfo.CurrentCulture):"—";
    }
    internal int? HandoffOrderId { get; private set; }
    internal bool RelatedChanged=>relatedChanged;

    private async void TasksClicked(object sender,EventArgs e)
    {
        if (repository is null || !tasksButton.Enabled)
            return;
        using var dialog=new CrmDealTasksForm(repository,id,canWriteTasks);
        dialog.ShowDialog(this);
        if (!dialog.Changed)
            return;
        await RefreshActivityAsync();
    }

    private async void CallsClicked(object sender,EventArgs e)
    {
        if (repository is null || !callsButton.Enabled)
            return;
        using var dialog=new CrmDealCallsForm(repository,id,canWriteTasks);
        dialog.ShowDialog(this);
        if (dialog.Changed)
            await RefreshActivityAsync();
    }

    private async void MeetingsClicked(object sender,EventArgs e)
    {
        if (repository is null || !meetingsButton.Enabled)
            return;
        using var dialog=new CrmDealMeetingsForm(repository,id,canWriteTasks);
        dialog.ShowDialog(this);
        if (dialog.Changed)
            await RefreshActivityAsync();
    }

    private async Task RefreshActivityAsync()
    {
        if (repository is null)
            return;
        relatedChanged=true;
        tasksButton.Enabled=callsButton.Enabled=meetingsButton.Enabled=false;
        var cancellation=lifetime.Token;
        try
        {
            var details=await repository.DetailAsync(id,false,cancellation);
            if (!cancellation.IsCancellationRequested)
            {
                historyGrid.DataSource=details.History;
                historyStatus.Text=details.History.Rows.Count==0?"No recorded deal history.":"";
                tasksButton.Enabled=callsButton.Enabled=meetingsButton.Enabled=details.CanReadTasks;
            }
        }
        catch(OperationCanceledException) when(cancellation.IsCancellationRequested) { }
        catch(Exception error) when(error is NpgsqlException or IOException or UnauthorizedAccessException
            or InvalidOperationException or TimeoutException)
        {
            if (!cancellation.IsCancellationRequested)
                historyStatus.Text="Activity saved. Reopen the deal to refresh its history.";
        }
    }

    internal void SelectNotes()
    {
        if (detailTabs.TabPages.Contains(notesTab))
            detailTabs.SelectedTab=notesTab;
    }

    private void BindNotes(CrmDealDetails details)
    {
        notesGrid.DataSource=details.Notes;
        notesStatus.Text=details.Notes.Rows.Count==0?"No visible notes.":"";
        notesWritable=details.CanAddNotes;
        NoteSelectionChanged(this,EventArgs.Empty);
    }

    private DataRowView? SelectedNote=>notesGrid.CurrentRow?.DataBoundItem as DataRowView;

    private void NoteSelectionChanged(object sender,EventArgs e)
    {
        var row=SelectedNote;
        noteBodyBox.Text=row is null?"":CrmDealRepository.RenderNote(Convert.ToString(row["body"])??"");
        addNoteButton.Enabled=notesWritable&&!notesBusy;
        editNoteButton.Enabled=pinNoteButton.Enabled=archiveNoteButton.Enabled=addNoteButton.Enabled&&row is not null;
        pinNoteButton.Text=row?["is_pinned"] is true?"Unpin":"Pin";
    }

    private async void AddNoteClicked(object sender,EventArgs e)
    {
        if (repository is null || !addNoteButton.Enabled)
            return;
        using var editor=new CrmDealNoteForm(repository,id);
        if (editor.ShowDialog(this)!=DialogResult.OK)
            return;
        await RefreshNotesAsync();
    }

    private async void EditNoteClicked(object sender,EventArgs e)
    {
        if (repository is null || !editNoteButton.Enabled || SelectedNote is not DataRowView row)
            return;
        using var editor=new CrmDealNoteForm(repository,id,(int)row["id"],(string)row["revision"],(string)row["body"]);
        if (editor.ShowDialog(this)==DialogResult.OK)
            await RefreshNotesAsync();
    }

    private async void PinNoteClicked(object sender,EventArgs e)
    {
        if (repository is null || !pinNoteButton.Enabled || SelectedNote is not DataRowView row)
            return;
        await RefreshNotesAsync(cancellation=>repository.PinDealNoteAsync(id,(int)row["id"],
            (string)row["revision"],row["is_pinned"] is not true,cancellation));
    }

    private async void ArchiveNoteClicked(object sender,EventArgs e)
    {
        if (repository is null || !archiveNoteButton.Enabled || SelectedNote is not DataRowView row ||
            MessageBox.Show(this,"Archive the selected note?","Deal notes",MessageBoxButtons.YesNo,
                MessageBoxIcon.Question,MessageBoxDefaultButton.Button2)!=DialogResult.Yes)
            return;
        await RefreshNotesAsync(cancellation=>repository.ArchiveDealNoteAsync(id,(int)row["id"],
            (string)row["revision"],cancellation));
    }

    private async Task RefreshNotesAsync(Func<CancellationToken,Task>? operation=null)
    {
        if (repository is null)
            return;
        notesBusy=true;
        NoteSelectionChanged(this,EventArgs.Empty);
        var cancellation=lifetime.Token;
        try
        {
            if (operation is not null)
                await operation(cancellation);
            relatedChanged=true;
            var refreshed=await repository.DetailAsync(id,false,cancellation);
            if (cancellation.IsCancellationRequested)
                return;
            BindNotes(refreshed);
            historyGrid.DataSource=refreshed.History;
            historyStatus.Text=refreshed.History.Rows.Count==0?"No recorded deal history.":"";
        }
        catch(OperationCanceledException) when (cancellation.IsCancellationRequested) { }
        catch(Exception error) when (error is NpgsqlException or IOException or UnauthorizedAccessException
            or InvalidOperationException or TimeoutException)
        {
            if (!cancellation.IsCancellationRequested)
                notesStatus.Text=error is InvalidOperationException or UnauthorizedAccessException?error.Message
                    :"Could not refresh the notes. Reopen the deal.";
        }
        finally
        {
            notesBusy=false;
            if (!cancellation.IsCancellationRequested)
                NoteSelectionChanged(this,EventArgs.Empty);
        }
    }

    private void CollaboratorsClicked(object sender,EventArgs e)
    {
        if (repository is null) return;
        using var form=new CrmDealCollaboratorsForm(repository,id);
        form.ShowDialog(this);
    }

    private void EditStakeholdersClicked(object sender,EventArgs e)
    {
        if (repository is null)
            return;
        using var editor=new CrmDealStakeholdersForm(repository,id);
        if (editor.ShowDialog(this)==DialogResult.OK)
        {
            DialogResult=DialogResult.OK;
            Close();
        }
    }

    private void CloseDealClicked(object sender,EventArgs e)
    {
        if (repository is null)
            return;
        using var editor=new CrmDealCloseForm(repository,id);
        if (editor.ShowDialog(this)==DialogResult.OK)
        {
            HandoffOrderId=editor.SalesOrderId;
            DialogResult=DialogResult.OK;
            Close();
        }
    }

    private void EditClicked(object sender,EventArgs e)
    {
        if (repository is null)
            return;
        using var editor=new CrmDealEditorForm(repository,id);
        if (editor.ShowDialog(this)==DialogResult.OK)
        {
            DialogResult=DialogResult.OK;
            Close();
        }
    }
}
