using System.Data;
using Telerik.WinControls.UI;

namespace Business_Suite;

internal sealed partial class PmsWorkspaceRecoveryForm : Form
{
    private readonly PmsProjectRepository? repository;
    private readonly CancellationTokenSource lifetime = new();
    private PmsWorkspaceRecoveryPreview? preview;
    private bool busy;

    public PmsWorkspaceRecoveryForm() => InitializeComponent();

    internal PmsWorkspaceRecoveryForm(PmsProjectRepository repository) : this()
    {
        this.repository = repository;
        UpdateActions();
    }

    internal bool WorkspacesChanged { get; private set; }
    private DataRow? Selected => (grid.CurrentRow?.DataBoundItem as DataRowView)?.Row;

    private async void RecoveryLoaded(object? sender, EventArgs e) => await RunAsync(ReadAsync);
    private async void RefreshClicked(object? sender, EventArgs e) => await RunAsync(ReadAsync);
    private void SelectionChanged(object sender, CurrentRowChangedEventArgs e) => UpdateActions();
    private void ConfirmationChanged(object? sender, EventArgs e) => UpdateActions();

    private async Task ReadAsync()
    {
        preview = await repository!.PreviewWorkspaceRecoveryAsync(lifetime.Token);
        if (lifetime.IsCancellationRequested)
            return;
        grid.DataSource = preview.Records.DefaultView;
        statusLabel.Text = $"{preview.ActiveCount:N0} active workspaces in this scope.";
    }

    private async void ResetClicked(object? sender, EventArgs e)
    {
        if (preview is null || !resetButton.Enabled)
            return;
        string fingerprint = preview.Fingerprint;
        await RunAsync(async () =>
        {
            int count = await repository!.ResetWorkspacesAsync(confirmationInput.Text, fingerprint, lifetime.Token);
            WorkspacesChanged = count > 0 || WorkspacesChanged;
            confirmationInput.Text = "";
            await ReadAsync();
            statusLabel.Text = $"{count:N0} workspaces archived.";
        });
    }

    private async void RestoreClicked(object? sender, EventArgs e)
    {
        if (!restoreButton.Enabled || Selected is not DataRow record)
            return;
        await RunAsync(async () =>
        {
            await repository!.RestoreWorkspaceAsync(record.Field<int>("id"), record.Field<string>("revision")!,
                lifetime.Token);
            WorkspacesChanged = true;
            await ReadAsync();
            statusLabel.Text = "Workspace restored.";
        });
    }

    private async Task RunAsync(Func<Task> work)
    {
        if (repository is null || busy)
            return;
        busy = true;
        UpdateActions();
        statusLabel.Text = "Working with workspace recovery…";
        try
        {
            await work();
        }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException
            or Npgsql.NpgsqlException or TimeoutException)
        {
            if (!lifetime.IsCancellationRequested)
                statusLabel.Text = error is InvalidOperationException or UnauthorizedAccessException
                    ? error.Message : "Could not complete the recovery action. Check PostgreSQL and refresh.";
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
        bool canChange = !busy && preview?.CanChange == true;
        confirmationInput.Enabled = canChange && preview!.ActiveCount > 0;
        resetButton.Enabled = confirmationInput.Enabled
            && confirmationInput.Text == PmsProjectRepository.ResetWorkspaceConfirmation;
        restoreButton.Enabled = canChange && Selected?.IsNull("deleted_at") == false;
        refreshButton.Enabled = closeButton.Enabled = !busy;
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
