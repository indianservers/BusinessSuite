using System.Data;
using Telerik.WinControls.UI;

namespace Business_Suite;

internal sealed partial class PmsRiskEditForm : Form
{
    private readonly PmsProjectRepository? repository;
    private readonly int project;
    private readonly int? risk;
    private readonly string? revision;
    private bool saving;

    public PmsRiskEditForm() => InitializeComponent();

    internal PmsRiskEditForm(PmsProjectRepository repository, int project, PmsRiskList choices, DataRow? row) : this()
    {
        this.repository = repository;
        this.project = project;
        Text = row is null ? "Add risk" : "Edit risk";
        risk = row?.Field<int>("id");
        revision = row?.Field<string>("revision");
        titleInput.Text = row?.Field<string>("title") ?? "";
        categoryInput.Text = row?.Field<string>("category") ?? "";
        descriptionInput.Text = row?.Field<string>("description") ?? "";
        mitigationInput.Text = row?.Field<string>("mitigation_plan") ?? "";
        contingencyInput.Text = row?.Field<string>("contingency_plan") ?? "";
        probabilityInput.Value = row?.Field<int?>("probability") ?? 3;
        impactInput.Value = row?.Field<int?>("impact") ?? 3;
        statusInput.SelectedValue = row?.Field<string>("status") ?? "open";
        var due = row?.Field<DateTime?>("due_date");
        if (due.HasValue)
            dueInput.Value = due.Value;
        dueInput.Checked = due.HasValue;
        BindChoice(ownerInput, choices.Owners, "Unassigned", row?.Field<int?>("owner_user_id"), "Keep existing owner");
        BindChoice(taskInput, choices.Tasks, "No linked task", row?.Field<int?>("linked_task_id"), "Previously linked task");
        UpdateScore();
    }

    private static void BindChoice(RadDropDownList input, DataTable choices, string empty, int? selected, string missing)
    {
        input.Items.Add(new RadListDataItem(empty));
        foreach (DataRow row in choices.Rows)
            input.Items.Add(new RadListDataItem(row.Field<string>("name")!) { Value = row.Field<int>("id") });
        if (selected.HasValue && !input.Items.Any(item => Equals(item.Value, selected.Value)))
            input.Items.Add(new RadListDataItem(missing) { Value = selected.Value });
        input.SelectedIndex = 0;
        if (selected.HasValue)
            input.SelectedValue = selected.Value;
    }

    private void ScoreChanged(object? sender, EventArgs e) => UpdateScore();

    private void UpdateScore()
    {
        int score = (int)probabilityInput.Value * (int)impactInput.Value;
        scoreLabel.Text = $"Score {score} · {(score >= 15 ? "High" : score >= 8 ? "Medium" : "Low")}";
    }

    private async void SaveClicked(object? sender, EventArgs e)
    {
        if (repository is null || saving)
            return;
        var draft = new PmsRiskDraft(titleInput.Text, NullIfEmpty(categoryInput.Text),
            (int)probabilityInput.Value, (int)impactInput.Value, statusInput.SelectedValue as string ?? "",
            dueInput.Checked ? dueInput.Value.Date : null, NullIfEmpty(descriptionInput.Text),
            NullIfEmpty(mitigationInput.Text), NullIfEmpty(contingencyInput.Text),
            ownerInput.SelectedValue is int selectedOwner ? selectedOwner : null,
            taskInput.SelectedValue is int selectedTask ? selectedTask : null);
        saving = true;
        saveButton.Enabled = cancelButton.Enabled = false;
        errorLabel.Text = "";
        bool saved = false;
        try
        {
            await repository.SaveRiskAsync(project, risk, revision, draft, CancellationToken.None);
            saved = true;
        }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException
            or Npgsql.NpgsqlException or TimeoutException)
        {
            errorLabel.Text = error is InvalidOperationException or UnauthorizedAccessException
                ? error.Message : "Could not save the risk. Check PostgreSQL and try again.";
        }
        finally
        {
            saving = false;
            saveButton.Enabled = cancelButton.Enabled = true;
        }
        if (saved)
            DialogResult = DialogResult.OK;
    }

    private static string? NullIfEmpty(string value) => value.Length == 0 ? null : value;

    protected override void OnFormClosing(FormClosingEventArgs e)
    {
        base.OnFormClosing(e);
        if (saving)
            e.Cancel = true;
    }
}
