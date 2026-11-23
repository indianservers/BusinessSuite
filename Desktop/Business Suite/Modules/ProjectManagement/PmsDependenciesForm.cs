using System.Data;
using System.Globalization;
using Telerik.WinControls.UI;

namespace Business_Suite;

internal sealed partial class PmsDependenciesForm : Form
{
    private readonly PmsProjectRepository? repository;
    private readonly int task;
    private readonly CancellationTokenSource lifetime = new();
    private PmsDependencyList? dependencies;
    private bool busy;
    private bool confirmRemoval;

    public PmsDependenciesForm() => InitializeComponent();

    internal PmsDependenciesForm(PmsProjectRepository repository, DataRow row) : this()
    {
        this.repository = repository;
        task = row.Field<int>("id");
        heading.Text = $"{row["task_key"]} · {row["title"]}";
    }

    private DataRow? Selected => (grid.CurrentRow?.DataBoundItem as DataRowView)?.Row;
    private async void DependenciesLoaded(object? sender, EventArgs e) => await RunAsync(ReadAsync);
    private async void RefreshClicked(object? sender, EventArgs e) => await RunAsync(ReadAsync);
    private void SelectionChanged(object sender, CurrentRowChangedEventArgs e) => UpdateActions();
    private void InputsChanged(object? sender, EventArgs e) => UpdateActions();

    private async Task ReadAsync()
    {
        dependencies = await repository!.ReadDependenciesAsync(task, lifetime.Token);
        var previous = otherTask.SelectedValue;
        grid.DataSource = dependencies.Rows.DefaultView;
        otherTask.DataSource = null;
        if (dependencies.CanEdit)
        {
            otherTask.DisplayMember = "label";
            otherTask.ValueMember = "id";
            otherTask.DataSource = dependencies.Candidates;
            otherTask.SelectedValue = previous;
        }
        status.Text = dependencies.Rows.Rows.Count == 0 ? "No dependencies."
            : $"{dependencies.Rows.Rows.Count:N0} dependencies";
    }

    private async void AddClicked(object? sender, EventArgs e)
    {
        if (otherTask.SelectedValue is not int other || !add.Enabled)
            return;
        if (!int.TryParse(lag.Text, NumberStyles.Integer, CultureInfo.CurrentCulture, out int lagDays))
        {
            status.Text = "Enter lag as a whole number of days.";
            return;
        }
        await RunAsync(async () =>
        {
            await repository!.ChangeDependencyAsync(task, dependencies!.Revision, other, direction.SelectedIndex == 0,
                kind.Text, lagDays, null, lifetime.Token);
            await ReadAsync();
        });
    }

    private void RemoveClicked(object? sender, EventArgs e)
    {
        if (!remove.Enabled)
            return;
        confirmRemoval = true;
        confirmation.Visible = true;
        UpdateActions();
    }

    private void CancelRemovalClicked(object? sender, EventArgs e)
    {
        confirmRemoval = false;
        confirmation.Visible = false;
        UpdateActions();
    }

    private async void ConfirmRemovalClicked(object? sender, EventArgs e)
    {
        if (!confirmRemoval || Selected is not DataRow row)
            return;
        confirmRemoval = false;
        confirmation.Visible = false;
        await RunAsync(async () =>
        {
            await repository!.ChangeDependencyAsync(task, dependencies!.Revision, 0, false, "", 0,
                row.Field<int>("id"), lifetime.Token);
            await ReadAsync();
        });
    }

    private async Task RunAsync(Func<Task> work)
    {
        if (repository is null || busy)
            return;
        busy = true;
        UpdateActions();
        status.Text = "Working with dependencies…";
        try { await work(); }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException
            or Npgsql.NpgsqlException or TimeoutException)
        {
            if (!lifetime.IsCancellationRequested)
                status.Text = error is InvalidOperationException or UnauthorizedAccessException ? error.Message
                    : "Could not update dependencies. Check PostgreSQL and retry.";
        }
        finally
        {
            busy = false;
            if (!lifetime.IsCancellationRequested)
                UpdateActions();
        }
    }

    private void UpdateActions()
    {
        bool ready = !busy && !confirmRemoval;
        grid.Enabled = refresh.Enabled = ready;
        close.Enabled = !busy;
        editor.Enabled = ready && dependencies?.CanEdit == true;
        add.Enabled = editor.Enabled && otherTask.SelectedValue is int;
        remove.Enabled = editor.Enabled && Selected is not null;
    }

    protected override void OnFormClosing(FormClosingEventArgs e)
    {
        base.OnFormClosing(e);
        if (busy)
            e.Cancel = true;
        if (!e.Cancel)
            lifetime.Cancel();
    }
}
