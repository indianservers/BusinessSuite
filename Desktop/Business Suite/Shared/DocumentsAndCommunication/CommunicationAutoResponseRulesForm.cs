using Npgsql;

namespace Business_Suite;

public sealed partial class CommunicationAutoResponseRulesForm : Form
{
    private readonly CommunicationDraftRepository? repository;
    private readonly CommunicationTemplatesRepository? templates;
    private AutoResponseRuleList? current;
    private bool busy;
    private bool reviewing;

    public CommunicationAutoResponseRulesForm() => InitializeComponent();

    internal CommunicationAutoResponseRulesForm(DesktopDatabaseSettings settings) : this()
    {
        repository = new(settings);
        templates = new(settings);
    }

    private async void RefreshClicked(object? sender, EventArgs e) => await RunAsync(LoadAsync);

    private async Task LoadAsync()
    {
        current = await repository!.AutoResponseRulesAsync(searchBox.Text);
        grid.DataSource = current.Rows;
        string notice = current.Rows.Count == 0 ? "No auto-response rules match the search." : $"{current.Rows.Count} rule(s).";
        if (current.CanCreate && templates is not null)
        {
            try
            {
                var available = await templates.ListAsync("", false);
                templateBox.DisplayMember = nameof(EmailTemplateRow.Name);
                templateBox.DataSource = available.Rows;
                if (available.Rows.Count == 0)
                    notice += " Enable an email template before creating a rule.";
            }
            catch (UnauthorizedAccessException)
            {
                templateBox.DataSource = null;
                notice += " Template access is required to create a rule.";
            }
        }
        feedback.Text = notice;
        reviewing = false;
    }

    private async void SaveClicked(object? sender, EventArgs e)
    {
        if (!saveButton.Enabled || templateBox.SelectedItem is not EmailTemplateRow template)
            return;
        var input = new AutoResponseRuleInput(nameBox.Text.Trim(), template.Id, activeBox.Checked);
        if (!reviewing)
        {
            reviewing = true;
            feedback.Text = $"Review {input.Name} with template {template.Name}. The rule will be {(input.Active ? "active" : "inactive")}.";
            UpdateButtons();
            return;
        }
        await RunAsync(async () =>
        {
            int id = await repository!.CreateAutoResponseRuleAsync(input);
            nameBox.Clear();
            activeBox.Checked = false;
            await LoadAsync();
            feedback.Text = $"Rule #{id} saved. It can be attached to a webform in the connected edition.";
        });
    }

    private void InputChanged(object? sender, EventArgs e)
    {
        reviewing = false;
        feedback.Text = "";
        UpdateButtons();
    }

    private async Task RunAsync(Func<Task> action)
    {
        if (busy || repository is null)
            return;
        busy = true;
        UpdateButtons();
        try { await action(); }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or ArgumentException or
            UnauthorizedAccessException or InvalidOperationException)
        {
            reviewing = false;
            feedback.Text = error is NpgsqlException or TimeoutException
                ? "Could not verify the rule action. Refresh before trying again." : error.Message;
        }
        finally
        {
            busy = false;
            UpdateButtons();
        }
    }

    private void UpdateButtons()
    {
        bool enabled = !busy && current?.CanCreate == true;
        refreshButton.Enabled = !busy;
        nameBox.Enabled = templateBox.Enabled = activeBox.Enabled = enabled;
        saveButton.Enabled = enabled && nameBox.Text.Trim().Length >= 2 && templateBox.SelectedItem is EmailTemplateRow;
        saveButton.Text = reviewing ? "Confirm and save" : "Review rule";
    }

    private void ClosingRules(object? sender, FormClosingEventArgs e) => e.Cancel = busy;
}
