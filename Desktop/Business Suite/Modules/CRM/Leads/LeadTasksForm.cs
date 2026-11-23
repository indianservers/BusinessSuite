using System.Data;
using Npgsql;

namespace Business_Suite;

public sealed partial class LeadTasksForm : Form
{
    private readonly LeadKey? key;
    private readonly CancellationTokenSource lifetime=new();
    private bool busy;

    public LeadTasksForm() => InitializeComponent();

    internal LeadTasksForm(LeadKey key,string name) : this()
    {
        this.key=key;
        heading.Text=name;
    }

    internal string SuccessMessage {get;private set;}="";

    private void LogActivityClicked(object sender,EventArgs e)
        => OpenActivityEditor(false);

    private void ScheduleFollowUpClicked(object sender,EventArgs e)
        => OpenActivityEditor(true);

    private void RescheduleFollowUpClicked(object sender,EventArgs e)
    {
        if (!rescheduleButton.Enabled || Selected is not DataRowView row)
            return;
        OpenActivityEditor(true,new((int)row["id"],(string)row["revision"],row["subject"] as string??"",
            row["activity_type"] as string??"",row["due"] as DateTime?,row["owner_user_id"] as int?));
    }

    private void OpenActivityEditor(bool scheduling,LeadFollowUpDraft? existing=null)
    {
        if (key is null || busy)
            return;
        using var dialog=new LeadActivityEntryForm(key,scheduling,existing);
        if (dialog.ShowDialog(this)==DialogResult.OK)
        {
            SuccessMessage=existing is not null?"Lead follow-up rescheduled.":
                scheduling?"Lead follow-up scheduled.":"Lead activity saved.";
            DialogResult=DialogResult.OK;
        }
    }

    private DataRowView? Selected => tasksGrid.CurrentRow?.DataBoundItem as DataRowView;

    private async void RefreshClicked(object sender,EventArgs e)
    {
        if (key is null || busy)
            return;
        var cancellation=lifetime.Token;
        busy=true;
        UpdateActions(this,EventArgs.Empty);
        feedback.Text="Loading Lead tasks…";
        try
        {
            var rows=await LeadStore.LeadTasksAsync(key.Id,cancellation);
            if (!cancellation.IsCancellationRequested)
            {
                tasksGrid.DataSource=rows;
                feedback.Text=rows.Rows.Count==0?"No tasks recorded for this Lead.":"Select a pending task to mark it complete.";
            }
        }
        catch(OperationCanceledException) when(cancellation.IsCancellationRequested) { }
        catch(Exception error) when(Expected(error))
        {
            if (!cancellation.IsCancellationRequested)
            {
                tasksGrid.DataSource=null;
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

    private void UpdateActions(object sender,EventArgs e)
    {
        refreshButton.Enabled=tasksGrid.Enabled=logActivityButton.Enabled=scheduleButton.Enabled=!busy;
        completeButton.Enabled=!busy&&Selected?["status"] is "Pending";
        rescheduleButton.Enabled=completeButton.Enabled&&Selected?["activity_type"] is ("call" or "email" or "meeting" or "task");
    }

    private async void CompleteClicked(object sender,EventArgs e)
    {
        if (key is null || !completeButton.Enabled || Selected is not DataRowView row)
            return;
        var cancellation=lifetime.Token;
        busy=true;
        UpdateActions(this,EventArgs.Empty);
        try
        {
            await LeadStore.CompleteLeadTaskAsync(key,(int)row["id"],(string)row["revision"],cancellation);
            if (!cancellation.IsCancellationRequested)
            {
                SuccessMessage="Lead task completed.";
                DialogResult=DialogResult.OK;
            }
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
    }

    private static bool Expected(Exception error) => error is NpgsqlException or IOException or InvalidOperationException or
        UnauthorizedAccessException or ArgumentException or TimeoutException;

    private static string Message(Exception error) => error is InvalidOperationException or UnauthorizedAccessException or ArgumentException
        ?error.Message:"Could not access Lead tasks in PostgreSQL.";

    private void FormIsClosed(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
}
