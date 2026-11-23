using System.Data;

namespace Business_Suite;

internal sealed partial class PmsScheduleMoveForm : Form
{
    private sealed record TaskOption(int Id, string Label, DateTime? Start, DateTime? Due);

    public PmsScheduleMoveForm() => InitializeComponent();

    internal PmsScheduleMoveForm(DataTable tasks, PmsScheduleMove? draft) : this()
    {
        var options = tasks.Rows.Cast<DataRow>().Select(row => new TaskOption(row.Field<int>("id"),
            $"{row["task_key"]} · {row["title"]}", row.Field<DateTime?>("start_date"), row.Field<DateTime?>("due_date"))).ToArray();
        task.DisplayMember = nameof(TaskOption.Label);
        task.ValueMember = nameof(TaskOption.Id);
        task.DataSource = options;
        if (draft is not null)
        {
            task.SelectedValue = draft.Task;
            start.Value = draft.Start;
            due.Value = draft.Due;
            start.Checked = due.Checked = true;
        }
        else
        {
            task.SelectedIndex = -1;
            SetDates(null);
        }
    }

    internal PmsScheduleMove? Proposal { get; private set; }

    private void TaskChanged(object? sender, Telerik.WinControls.UI.Data.PositionChangedEventArgs e) =>
        SetDates(task.SelectedItem?.DataBoundItem as TaskOption);

    private void SetDates(TaskOption? selected)
    {
        start.Value = selected?.Start ?? DateTime.Today;
        due.Value = selected?.Due ?? DateTime.Today;
        start.Checked = selected?.Start.HasValue == true;
        due.Checked = selected?.Due.HasValue == true;
        preview.Enabled = selected is not null;
        status.Text = "";
    }

    private void PreviewClicked(object? sender, EventArgs e)
    {
        if (task.SelectedValue is not int selected)
            return;
        if (!start.Checked || !due.Checked || due.Value.Date < start.Value.Date)
        {
            status.Text = "Choose a start date and a due date on or after it.";
            return;
        }
        Proposal = new PmsScheduleMove(selected, start.Value.Date, due.Value.Date);
        DialogResult = DialogResult.OK;
    }
}
