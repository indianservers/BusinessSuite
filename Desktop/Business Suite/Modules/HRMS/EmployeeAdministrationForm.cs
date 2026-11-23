using System.Data;
using Telerik.WinControls.UI;

namespace Business_Suite;

public sealed partial class EmployeeAdministrationForm : Form
{
    private readonly EmployeeAdministrationRepository? repository;
    private readonly CancellationTokenSource lifetime = new();
    private DataRow? editing;
    private bool loading;
    private bool saving;

    public EmployeeAdministrationForm() => InitializeComponent();

    internal EmployeeAdministrationForm(DesktopDatabaseSettings settings) : this()
    {
        repository = new EmployeeAdministrationRepository(settings);
    }

    private DataRow? Selected => (employeeGrid.CurrentRow?.DataBoundItem as DataRowView)?.Row;
    private async void EmployeeAdministrationLoaded(object? sender, EventArgs e) => await ReloadAsync();
    private async void SearchClicked(object? sender, EventArgs e) => await ReloadAsync();

    private async void SearchKeyDown(object? sender, KeyEventArgs e)
    {
        if (e.KeyCode != Keys.Enter)
            return;
        e.SuppressKeyPress = true;
        await ReloadAsync();
    }

    private async Task ReloadAsync(int? selectId = null)
    {
        if (repository is null || loading || editing is not null)
            return;
        loading = true;
        UpdateActions();
        statusLabel.Text = "Loading employee records…";
        try
        {
            var employees = await repository.ListAsync(searchInput.Text, lifetime.Token);
            if (lifetime.IsCancellationRequested)
                return;
            employeeGrid.DataSource = employees.DefaultView;
            if (selectId.HasValue)
                employeeGrid.CurrentRow = employeeGrid.Rows.FirstOrDefault(row =>
                    row.DataBoundItem is DataRowView view && view.Row.Field<int>("id") == selectId.Value);
            statusLabel.Text = employees.Rows.Count switch
            {
                0 => "No employees match your search.",
                1 => "1 employee",
                2000 => "Showing up to 2,000 employees. Narrow the search for more results.",
                _ => $"{employees.Rows.Count:N0} employees"
            };
        }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (error is Npgsql.NpgsqlException or TimeoutException
            or InvalidOperationException or UnauthorizedAccessException)
        {
            if (!lifetime.IsCancellationRequested)
            {
                employeeGrid.DataSource = null;
                statusLabel.Text = error is InvalidOperationException or UnauthorizedAccessException
                    ? error.Message : "Could not load employee records from PostgreSQL.";
            }
        }
        finally
        {
            loading = false;
            if (!lifetime.IsCancellationRequested)
                UpdateActions();
        }
    }

    private void EmployeeSelectionChanged(object? sender, CurrentRowChangedEventArgs e) => UpdateActions();

    private async void LifecycleClicked(object? sender, EventArgs e)
    {
        if (repository is null || Selected is not DataRow employee || !lifecycleButton.Enabled)
            return;
        int id = employee.Field<int>("id");
        using var lifecycle = new EmployeeLifecycleForm(repository, employee);
        if (lifecycle.ShowDialog(this) == DialogResult.OK)
            await ReloadAsync(id);
    }

    private async void DocumentsClicked(object? sender, EventArgs e)
    {
        if (repository is null || Selected is not DataRow row || !documentsButton.Enabled)
            return;
        using var documents = new EmployeeDocumentsForm(repository, row);
        documents.ShowDialog(this);
        await ReloadAsync(row.Field<int>("id"));
    }

    private async void QuickAddClicked(object? sender, EventArgs e)
    {
        if (repository is null || !quickAddButton.Enabled)
            return;
        using var quickAdd = new EmployeeQuickAddForm(repository);
        if (quickAdd.ShowDialog(this) == DialogResult.OK)
        {
            searchInput.Clear();
            await ReloadAsync(quickAdd.EmployeeId);
        }
    }

    private async void ChecksClicked(object? sender, EventArgs e)
    {
        if (repository is null || Selected is not DataRow row || !checksButton.Enabled)
            return;
        using var checks = new EmployeeProfileChecksForm(repository, row);
        checks.ShowDialog(this);
        await ReloadAsync(row.Field<int>("id"));
    }

    private void HistoryClicked(object? sender, EventArgs e)
    {
        if (repository is null || Selected is not DataRow row || !historyButton.Enabled)
            return;
        using var history = new EmployeeProfileHistoryForm(repository, row);
        history.ShowDialog(this);
    }

    private async void CertificationsClicked(object? sender, EventArgs e)
    {
        if (repository is null || Selected is not DataRow row || !certificationButton.Enabled)
            return;
        using var certifications = new EmployeeCertificationForm(repository, row);
        certifications.ShowDialog(this);
        await ReloadAsync(row.Field<int>("id"));
    }

    private async void ExperienceClicked(object? sender, EventArgs e)
    {
        if (repository is null || Selected is not DataRow row || !experienceButton.Enabled)
            return;
        using var experience = new EmployeeExperienceForm(repository, row);
        experience.ShowDialog(this);
        await ReloadAsync(row.Field<int>("id"));
    }

    private async void SkillsClicked(object? sender, EventArgs e)
    {
        if (repository is null || Selected is not DataRow row || !skillsButton.Enabled)
            return;
        using var skills = new EmployeeSkillsForm(repository, row);
        skills.ShowDialog(this);
        await ReloadAsync(row.Field<int>("id"));
    }

    private async void EducationClicked(object? sender, EventArgs e)
    {
        if (repository is null || Selected is not DataRow row || !educationButton.Enabled)
            return;
        using var education = new EmployeeEducationForm(repository, row);
        education.ShowDialog(this);
        await ReloadAsync(row.Field<int>("id"));
    }

    private async void ArchiveClicked(object? sender, EventArgs e)
    {
        if (repository is null || Selected is not DataRow row || !archiveButton.Enabled ||
            MessageBox.Show(this, $"Archive {row["employee_name"]}? The record will be removed from active employee lists.",
                "Archive employee", MessageBoxButtons.YesNo, MessageBoxIcon.Question,
                MessageBoxDefaultButton.Button2) != DialogResult.Yes)
            return;
        saving = true;
        UpdateActions();
        statusLabel.Text = "Archiving employee…";
        bool archived = false;
        try
        {
            await repository.ArchiveAsync(row.Field<int>("id"), row.Field<string>("employment_revision")!, lifetime.Token);
            archived = true;
        }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException
            or Npgsql.NpgsqlException or TimeoutException)
        {
            statusLabel.Text = error is InvalidOperationException or UnauthorizedAccessException ? error.Message
                : "Could not archive the employee. Check PostgreSQL and retry.";
        }
        finally
        {
            saving = false;
            UpdateActions();
        }
        if (archived)
            await ReloadAsync();
    }

    private void EmployeeDoubleClicked(object? sender, GridViewCellEventArgs e)
    {
        if (e.Row is GridViewDataRowInfo && editButton.Enabled)
            EditClicked(sender, e);
    }

    private void EditClicked(object? sender, EventArgs e)
    {
        if (Selected is not DataRow employee || !editButton.Enabled)
            return;
        editing = employee;
        selectedLabel.Text = employee.Field<string>("employee_name");
        displayInput.Text = employee.Field<string>("preferred_display_name") ?? "";
        extensionInput.Text = employee.Field<string>("office_extension") ?? "";
        deskInput.Text = employee.Field<string>("desk_code") ?? "";
        SelectValue(locationInput, employee.Field<string>("work_location"), 6);
        SelectValue(visibilityInput, employee.Field<string>("directory_visibility"), 3);
        statusLabel.Text = "";
        UpdateActions();
        displayInput.Focus();
    }

    private static void SelectValue(RadDropDownList editor, string? value, int designItemCount)
    {
        while (editor.Items.Count > designItemCount)
            editor.Items.RemoveAt(editor.Items.Count - 1);
        var item = editor.Items.FirstOrDefault(candidate => Equals(candidate.Value, value));
        if (item is null)
        {
            item = new RadListDataItem(value ?? "Unspecified") { Value = value };
            editor.Items.Add(item);
        }
        editor.SelectedItem = item;
    }

    private async void SaveClicked(object? sender, EventArgs e)
    {
        if (repository is null || editing is not DataRow employee || saving)
            return;
        int id = employee.Field<int>("id");
        string revision = employee.Field<string>("revision")!;
        var draft = new EmployeeAdministrationDraft(
            Value(displayInput.Text, employee.Field<string>("preferred_display_name")),
            locationInput.SelectedValue as string,
            Value(extensionInput.Text, employee.Field<string>("office_extension")),
            Value(deskInput.Text, employee.Field<string>("desk_code")),
            visibilityInput.SelectedValue as string);
        saving = true;
        UpdateActions();
        statusLabel.Text = "Saving employee profile…";
        bool saved = false;
        try
        {
            await repository.SaveAsync(id, revision, draft, lifetime.Token);
            saved = true;
            editing = null;
        }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (error is Npgsql.NpgsqlException or TimeoutException
            or InvalidOperationException or UnauthorizedAccessException)
        {
            if (!lifetime.IsCancellationRequested)
                statusLabel.Text = error is InvalidOperationException or UnauthorizedAccessException
                    ? error.Message : "Could not save the employee profile. Check the PostgreSQL connection and retry.";
        }
        finally
        {
            saving = false;
            if (!lifetime.IsCancellationRequested)
                UpdateActions();
        }
        if (saved && !lifetime.IsCancellationRequested)
            await ReloadAsync(id);
    }

    private static string? Value(string current, string? original) =>
        current.Length == 0 && original is null ? null : current;

    private void CancelClicked(object? sender, EventArgs e)
    {
        editing = null;
        statusLabel.Text = "";
        UpdateActions();
    }

    private void UpdateActions()
    {
        bool idle = !loading && !saving;
        searchInput.Enabled = searchButton.Enabled = employeeGrid.Enabled = idle && editing is null;
        quickAddButton.Enabled = searchButton.Enabled;
        lifecycleButton.Enabled = searchButton.Enabled && Selected is not null;
        documentsButton.Enabled = checksButton.Enabled = historyButton.Enabled = certificationButton.Enabled = experienceButton.Enabled = skillsButton.Enabled = educationButton.Enabled = lifecycleButton.Enabled;
        archiveButton.Enabled = lifecycleButton.Enabled && Selected?.Field<bool>("can_write") == true
            && Selected.Field<bool>("can_archive") && !Selected.Field<bool>("linked_login");
        editButton.Enabled = lifecycleButton.Enabled && Selected?.Field<bool>("can_write") == true;
        editor.Enabled = idle && editing is not null;
    }

    protected override void OnFormClosing(FormClosingEventArgs e)
    {
        base.OnFormClosing(e);
        if (saving)
            e.Cancel = true;
        if (!e.Cancel)
            lifetime.Cancel();
    }
}
