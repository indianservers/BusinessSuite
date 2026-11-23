using System.Data;
using System.Globalization;
using Telerik.WinControls.UI;

namespace Business_Suite;

internal sealed partial class PmsTaskEditForm : Form
{
    private readonly PmsProjectRepository? repository;
    private readonly int taskId;
    private readonly int? projectId;
    private readonly string? createKey;
    private readonly string? revision;
    private readonly string? initialDescription;
    private bool saving;

    public PmsTaskEditForm()
    {
        InitializeComponent();
    }

    internal PmsTaskEditForm(PmsProjectRepository repository, DataRow task) : this()
    {
        this.repository = repository;
        taskId = task.Field<int>("id");
        revision = task.Field<string>("revision");
        keyInput.Text = task.Field<string>("task_key") ?? "";
        titleInput.Text = task.Field<string>("title") ?? "";
        initialDescription = task.Field<string>("description");
        descriptionInput.Text = initialDescription ?? "";
        SelectExisting(statusInput, task.Field<string>("status"));
        SelectExisting(priorityInput, task.Field<string>("priority"));
        SetDate(startInput, task.Field<DateTime?>("start_date"));
        SetDate(dueInput, task.Field<DateTime?>("due_date"));
        hoursInput.Text = task.Field<decimal?>("estimated_hours")?.ToString("0.##", CultureInfo.CurrentCulture) ?? "";
    }

    internal PmsTaskEditForm(PmsProjectRepository repository, int projectId, string projectName) : this()
    {
        this.repository = repository;
        this.projectId = projectId;
        createKey = "T-" + Guid.NewGuid().ToString("N").Substring(0, 12).ToUpperInvariant();
        Text = "New task";
        saveButton.Text = "Create";
        keyLabel.Text = "Project";
        keyInput.Text = projectName;
        SelectExisting(statusInput, "To Do");
        SelectExisting(priorityInput, "Medium");
    }

    private static void SelectExisting(RadDropDownList editor, string? value)
    {
        if (value is null)
            return;
        var match = editor.Items.FirstOrDefault(item => item.Text == value);
        if (match is null)
        {
            match = new RadListDataItem(value);
            editor.Items.Add(match);
        }
        editor.SelectedItem = match;
    }

    private static void SetDate(RadDateTimePicker editor, DateTime? date)
    {
        if (date.HasValue)
            editor.Value = date.Value;
        editor.Checked = date.HasValue;
    }

    private async void SaveClicked(object sender, EventArgs e)
    {
        if (saving || repository is null || (revision is null && !projectId.HasValue))
            return;

        var hoursText = hoursInput.Text.Trim();
        decimal? hours = null;
        if (hoursText.Length > 0)
        {
            if (!decimal.TryParse(hoursText, NumberStyles.Number, CultureInfo.CurrentCulture, out var entered))
            {
                errorLabel.Text = "Enter a valid number of hours.";
                hoursInput.Focus();
                return;
            }
            hours = entered;
        }

        string? description = descriptionInput.Text.Length == 0 && initialDescription is null
            ? null : descriptionInput.Text;
        var draft = new PmsTaskDraft(titleInput.Text.Trim(), description,
            statusInput.SelectedItem?.Text, priorityInput.SelectedItem?.Text,
            startInput.Checked ? startInput.Value.Date : null, dueInput.Checked ? dueInput.Value.Date : null, hours);
        saving = true;
        errorLabel.Text = "";
        saveButton.Enabled = cancelButton.Enabled = false;
        try
        {
            if (projectId.HasValue)
                await repository.CreateTaskAsync(projectId.Value, createKey!, draft, CancellationToken.None);
            else
                await repository.SaveTaskAsync(taskId, revision!, draft, CancellationToken.None);
            DialogResult = DialogResult.OK;
        }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException
            or Npgsql.NpgsqlException)
        {
            errorLabel.Text = error is Npgsql.NpgsqlException
                ? "The task could not be saved. Check the PostgreSQL connection and try again."
                : error.Message;
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
