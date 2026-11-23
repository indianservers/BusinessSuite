using System.Data;

namespace Business_Suite;

internal sealed partial class PmsTaskAssignmentForm : Form
{
    private sealed record Person(int Id, string Name, bool Protected, bool Eligible)
    {
        public override string ToString() => Protected ? Name + " · Batch controlled" : Name;
    }

    private readonly PmsProjectRepository? repository;
    private readonly int task;
    private readonly CancellationTokenSource lifetime = new();
    private string? revision;
    private bool binding;
    private bool saving;

    public PmsTaskAssignmentForm() => InitializeComponent();

    internal PmsTaskAssignmentForm(PmsProjectRepository repository, DataRow row) : this()
    {
        this.repository = repository;
        task = row.Field<int>("id");
        heading.Text = $"{row["task_key"]} · {row["title"]}";
    }

    private async void AssignmentLoaded(object? sender, EventArgs e)
    {
        if (repository is null)
            return;
        statusLabel.Text = "Loading project collaborators…";
        try
        {
            var result = await repository.LoadTaskAssignmentsAsync(task, lifetime.Token);
            if (lifetime.IsCancellationRequested)
                return;
            binding = true;
            foreach (DataRow row in result.People.Rows)
                peopleList.Items.Add(new Person(row.Field<int>("id"), row.Field<string>("person")!,
                    row.Field<bool>("protected"), row.Field<bool>("eligible")), row.Field<bool>("assigned"));
            revision = result.Revision;
            statusLabel.Text = peopleList.Items.Count == 0 ? "No eligible project collaborators were found." : "";
            saveButton.Enabled = true;
        }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException
            or Npgsql.NpgsqlException or TimeoutException)
        {
            if (!lifetime.IsCancellationRequested)
                statusLabel.Text = error is InvalidOperationException or UnauthorizedAccessException
                    ? error.Message : "Could not load task assignments from PostgreSQL.";
        }
        finally
        {
            binding = false;
        }
    }

    private void PersonChecked(object? sender, ItemCheckEventArgs e)
    {
        if (binding || peopleList.Items[e.Index] is not Person person)
            return;
        if (person.Protected || (!person.Eligible && e.NewValue == CheckState.Checked))
        {
            e.NewValue = e.CurrentValue;
            statusLabel.Text = person.Protected
                ? "Batch-controlled assignments are managed through Batch controls."
                : "This person no longer has access to the project.";
        }
    }

    private async void SaveClicked(object? sender, EventArgs e)
    {
        if (repository is null || revision is null || saving)
            return;
        var chosen = peopleList.CheckedItems.Cast<Person>().Select(person => person.Id).ToArray();
        saving = true;
        SetControls(false);
        statusLabel.Text = "Saving assignments…";
        bool saved = false;
        try
        {
            await repository.SaveTaskAssignmentsAsync(task, revision, chosen, noteInput.Text, notifyInput.Checked,
                lifetime.Token);
            saved = true;
        }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException
            or Npgsql.NpgsqlException or TimeoutException)
        {
            statusLabel.Text = error is InvalidOperationException or UnauthorizedAccessException
                ? error.Message : "Could not save assignments. Check the PostgreSQL connection and try again.";
        }
        finally
        {
            saving = false;
            SetControls(true);
        }
        if (saved)
            DialogResult = DialogResult.OK;
    }

    private void SetControls(bool enabled) =>
        peopleList.Enabled = noteInput.Enabled = notifyInput.Enabled = saveButton.Enabled = cancelButton.Enabled = enabled;

    protected override void OnFormClosing(FormClosingEventArgs e)
    {
        base.OnFormClosing(e);
        if (saving)
            e.Cancel = true;
        if (!e.Cancel)
            lifetime.Cancel();
    }
}
