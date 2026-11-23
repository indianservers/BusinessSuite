using System.Data;
using System.Globalization;
using Telerik.WinControls.UI;

namespace Business_Suite;

internal sealed partial class PmsProjectEditForm : Form
{
    private PmsProjectRepository? repository;
    private int? projectId;
    private string? revision;
    private PmsProjectScope scope;
    private bool saving;

    public PmsProjectEditForm()
    {
        InitializeComponent();
    }

    internal PmsProjectEditForm(PmsProjectRepository repository, IEnumerable<PmsWorkspaceChoice> workspaces,
        int selectedWorkspaceId, DataRow? project, PmsProjectScope scope) : this()
    {
        this.repository = repository;
        this.scope = scope;
        Text = project is null ? "New project" : "Edit project";
        foreach (var workspace in workspaces.Where(choice => choice.CanManage || project is not null))
            workspaceInput.Items.Add(new RadListDataItem(workspace.Name) { Value = workspace.Id });
        workspaceInput.SelectedValue = selectedWorkspaceId;

        if (project is null)
        {
            keyInput.Text = "PRJ" + Guid.NewGuid().ToString("N").Substring(0, 6).ToUpperInvariant();
            statusInput.SelectedIndex = 2;
            priorityInput.SelectedIndex = 1;
            if (workspaceInput.SelectedIndex < 0 && workspaceInput.Items.Count == 1)
                workspaceInput.SelectedIndex = 0;
            return;
        }

        projectId = project.Field<int>("id");
        revision = project.Field<string>("revision");
        workspaceInput.Enabled = false;
        keyInput.Enabled = false;
        keyInput.Text = project.Field<string>("project_key") ?? "";
        nameInput.Text = project.Field<string>("name") ?? "";
        descriptionInput.Text = project.Field<string>("description") ?? "";
        statusInput.SelectedIndex = FindText(statusInput, project.Field<string>("status"));
        priorityInput.SelectedIndex = FindText(priorityInput, project.Field<string>("priority"));
        SetDate(startInput, project.Field<DateTime?>("start_date"));
        SetDate(dueInput, project.Field<DateTime?>("due_date"));
        budgetInput.Text = project.Field<decimal?>("budget_amount")?.ToString("0.00", CultureInfo.CurrentCulture) ?? "";
    }

    private static int FindText(RadDropDownList editor, string? value)
    {
        for (var index = 0; index < editor.Items.Count; index++)
            if (editor.Items[index].Text == value)
                return index;
        return -1;
    }

    private static void SetDate(RadDateTimePicker editor, DateTime? date)
    {
        if (date.HasValue)
            editor.Value = date.Value;
        editor.Checked = date.HasValue;
    }

    private async void saveButton_Click(object sender, EventArgs e)
    {
        if (saving || repository is null)
            return;
        errorLabel.Text = "";
        decimal? budget = null;
        if (!string.IsNullOrWhiteSpace(budgetInput.Text))
        {
            if (!decimal.TryParse(budgetInput.Text, NumberStyles.Number, CultureInfo.CurrentCulture, out var value))
            {
                errorLabel.Text = "Enter a valid budget amount.";
                budgetInput.Focus();
                return;
            }
            budget = value;
        }

        var draft = new PmsProjectDraft(workspaceInput.SelectedValue is int workspaceId ? workspaceId : 0,
            keyInput.Text.Trim(), nameInput.Text.Trim(), descriptionInput.Text, statusInput.SelectedItem?.Text ?? "",
            priorityInput.SelectedItem?.Text ?? "", startInput.Checked ? startInput.Value.Date : null,
            dueInput.Checked ? dueInput.Value.Date : null, budget);

        saving = true;
        saveButton.Enabled = cancelButton.Enabled = false;
        try
        {
            await repository.SaveAsync(draft, projectId, revision, scope, CancellationToken.None);
            DialogResult = DialogResult.OK;
        }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException)
        {
            errorLabel.Text = error.Message;
        }
        catch (Npgsql.NpgsqlException)
        {
            errorLabel.Text = "The project could not be saved. Check the PostgreSQL connection and try again.";
        }
        finally
        {
            saving = false;
            saveButton.Enabled = cancelButton.Enabled = true;
        }
    }

    protected override void OnFormClosing(FormClosingEventArgs e)
    {
        base.OnFormClosing(e);
        if (saving && DialogResult != DialogResult.OK)
            e.Cancel = true;
    }
}
