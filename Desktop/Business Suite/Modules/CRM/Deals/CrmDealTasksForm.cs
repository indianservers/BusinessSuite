using System.Data;
using Npgsql;

namespace Business_Suite;

public sealed partial class CrmDealTasksForm : Form
{
    private readonly CrmDealRepository? repository;
    private readonly int dealId;
    private readonly bool canWrite;
    private readonly CancellationTokenSource lifetime=new();
    private bool busy;
    private bool loaded;
    private (int Id,string Revision)? editing;

    public CrmDealTasksForm() => InitializeComponent();
    internal CrmDealTasksForm(CrmDealRepository repository,int dealId,bool canWrite) : this()
    {
        this.repository=repository;
        this.dealId=dealId;
        this.canWrite=canWrite;
    }

    internal bool Changed {get;private set;}
    private DataRowView? Selected=>grid.CurrentRow?.DataBoundItem as DataRowView;

    private async void FormShown(object sender,EventArgs e) => await RunAsync(_=>Task.CompletedTask);
    private void SelectionChanged(object sender,EventArgs e) => UpdateActions();

    private async void AddClicked(object sender,EventArgs e)
    {
        if (!canWrite || repository is null)
            return;
        await RunAsync(async cancellation =>
        {
            var task=new DealTaskDraft(titleBox.Text,descriptionBox.Text,priorityBox.Text,Date(dueBox),Date(reminderBox));
            if (editing is { } selected)
                await repository.SaveDealTaskAsync(dealId,selected.Id,selected.Revision,task,cancellation);
            else
                await repository.AddDealTaskAsync(dealId,task,cancellation);
            Changed=true;
            ClearEditor();
        });

        static DateTime? Date(DateTimePicker date)
        {
            if (!date.Checked) return null;
            DateTime local=DateTime.SpecifyKind(date.Value,DateTimeKind.Unspecified);
            if (TimeZoneInfo.Local.IsInvalidTime(local))
                throw new ArgumentException("A selected time does not exist in the local time zone.");
            return TimeZoneInfo.ConvertTimeToUtc(local,TimeZoneInfo.Local);
        }
    }

    private void EditClicked(object sender,EventArgs e)
    {
        if (!editButton.Enabled || Selected is not DataRowView row)
            return;
        try
        {
            LoadDate(dueBox,row["due_date"]);
            LoadDate(reminderBox,row["reminder_at"]);
        }
        catch(ArgumentOutOfRangeException)
        {
            feedback.Text="An existing task date is outside the date picker's range.";
            return;
        }
        editing=((int)row["id"],(string)row["revision"]);
        titleBox.Text=Convert.ToString(row["title"]);
        descriptionBox.Text=Convert.ToString(row["description"]);
        string priority=Convert.ToString(row["priority"])??"";
        priorityBox.SelectedIndex=priorityBox.Items.Contains(priority)?priorityBox.Items.IndexOf(priority):1;
        feedback.Text=$"Editing task #{editing.Value.Id}.";
        UpdateActions();

        static void LoadDate(DateTimePicker box,object value)
        {
            if (value is DateTime timestamp)
            {
                box.Value=DateTime.SpecifyKind(timestamp,DateTimeKind.Utc).ToLocalTime();
                box.Checked=true;
            }
            else box.Checked=false;
        }
    }

    private void CancelEditClicked(object sender,EventArgs e)
    {
        ClearEditor();
        feedback.Text="";
        UpdateActions();
    }

    private void ClearEditor()
    {
        editing=null;
        titleBox.Clear();
        descriptionBox.Clear();
        dueBox.Checked=reminderBox.Checked=false;
        priorityBox.SelectedIndex=1;
    }

    private async void ArchiveClicked(object sender,EventArgs e)
    {
        if (!archiveButton.Enabled || repository is null || Selected is not DataRowView row)
            return;
        if (MessageBox.Show(this,$"Archive {row["title"]}?","Deal tasks",MessageBoxButtons.YesNo,
            MessageBoxIcon.Question,MessageBoxDefaultButton.Button2)!=DialogResult.Yes)
            return;
        await RunAsync(async cancellation=>
        {
            await repository.ArchiveDealTaskAsync(dealId,(int)row["id"],(string)row["revision"],cancellation);
            Changed=true;
        });
    }

    private async void CompleteClicked(object sender,EventArgs e)
    {
        if (!canWrite || repository is null || Selected is not DataRowView row)
            return;
        await RunAsync(async cancellation =>
        {
            await repository.CompleteDealTaskAsync(dealId,(int)row["id"],(string)row["revision"],cancellation);
            Changed=true;
        });
    }

    private async Task RunAsync(Func<CancellationToken,Task> operation)
    {
        if (busy || repository is null)
            return;
        var cancellation=lifetime.Token;
        busy=true;
        UpdateActions();
        try
        {
            await operation(cancellation);
            var rows=await repository.DealTasksAsync(dealId,cancellation);
            if (!cancellation.IsCancellationRequested)
            {
                grid.DataSource=rows;
                loaded=true;
                feedback.Text=rows.Rows.Count==0?"No tasks for this deal.":"";
            }
        }
        catch(OperationCanceledException) when(cancellation.IsCancellationRequested) { }
        catch(Exception error) when(error is NpgsqlException or ArgumentException or InvalidOperationException
            or UnauthorizedAccessException or IOException or TimeoutException)
        {
            if (!cancellation.IsCancellationRequested)
                feedback.Text=error is InvalidOperationException or ArgumentException or UnauthorizedAccessException
                    ?error.Message:"Could not complete the task operation. Check PostgreSQL.";
        }
        finally
        {
            busy=false;
            if (!cancellation.IsCancellationRequested)
                UpdateActions();
        }
    }

    private void UpdateActions()
    {
        addButton.Enabled=loaded&&canWrite&&!busy;
        addButton.Text=editing.HasValue?"Save task":"Add task";
        editButton.Enabled=addButton.Enabled&&!editing.HasValue&&Selected is DataRowView row &&
            (Convert.ToString(row["status"])??"").ToLowerInvariant() is not ("done" or "completed" or "complete" or "cancelled" or "canceled");
        completeButton.Enabled=editButton.Enabled;
        archiveButton.Enabled=loaded&&canWrite&&!busy&&!editing.HasValue&&Selected is not null;
        cancelEditButton.Enabled=editing.HasValue&&!busy;
        titleBox.Enabled=descriptionBox.Enabled=priorityBox.Enabled=dueBox.Enabled=reminderBox.Enabled=addButton.Enabled;
        closeButton.Enabled=!busy;
    }

    private void FormIsClosing(object sender,FormClosingEventArgs e) => e.Cancel=busy;
    private void FormIsClosed(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
}
