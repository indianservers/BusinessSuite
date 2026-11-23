using System.Data;

namespace Business_Suite;

internal sealed partial class PmsProjectCloneForm : Form
{
    private readonly PmsProjectRepository? repository;
    private readonly int source;
    private readonly string? revision;
    private readonly PmsProjectScope scope;
    private bool saving;

    public PmsProjectCloneForm() => InitializeComponent();

    internal PmsProjectCloneForm(PmsProjectRepository repository, DataRow project, PmsProjectScope scope) : this()
    {
        this.repository = repository;
        this.scope = scope;
        source = project.Field<int>("id");
        revision = project.Field<string>("revision");
        var originalName = project.Field<string>("name") ?? "";
        nameInput.Text = originalName.Substring(0, Math.Min(originalName.Length, 175)) + " copy";
        statusLabel.Text = "The duplicate starts Planned. Copied tasks start in To Do.";
    }

    private void TasksChanged(object? sender, EventArgs e) => dependenciesInput.Enabled = tasksInput.Checked && !saving;

    private async void SaveClicked(object? sender, EventArgs e)
    {
        if (repository is null || revision is null || saving)
            return;
        var draft = new PmsProjectCloneDraft(nameInput.Text, keyInput.Text, tasksInput.Checked, datesInput.Checked,
            teamInput.Checked, attachmentsInput.Checked, milestonesInput.Checked, tasksInput.Checked && dependenciesInput.Checked);
        saving = true;
        SetInputs(false);
        statusLabel.Text = "Duplicating project…";
        bool saved = false;
        try
        {
            await repository.CloneProjectAsync(source, revision, scope, draft, CancellationToken.None);
            saved = true;
        }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException
            or Npgsql.NpgsqlException or TimeoutException)
        {
            statusLabel.Text = error is InvalidOperationException or UnauthorizedAccessException
                ? error.Message : "Could not duplicate the project. Refresh the source and try again.";
        }
        finally
        {
            saving = false;
            SetInputs(true);
        }
        if (saved)
            DialogResult = DialogResult.OK;
    }

    private void SetInputs(bool enabled)
    {
        nameInput.Enabled = keyInput.Enabled = tasksInput.Enabled = datesInput.Enabled = teamInput.Enabled =
            attachmentsInput.Enabled = milestonesInput.Enabled = saveButton.Enabled = closeButton.Enabled = enabled;
        dependenciesInput.Enabled = enabled && tasksInput.Checked;
    }

    protected override void OnFormClosing(FormClosingEventArgs e)
    {
        base.OnFormClosing(e);
        if (saving)
            e.Cancel = true;
    }
}
