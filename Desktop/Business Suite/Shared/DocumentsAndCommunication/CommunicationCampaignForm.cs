using Npgsql;

namespace Business_Suite;

public sealed partial class CommunicationCampaignForm : Form
{
    private readonly CommunicationDraftRepository? repository;
    private readonly CommunicationTemplatesRepository? templates;
    private CampaignList? list;
    private EmailCampaign? selected;
    private bool isNew;
    private bool busy;
    private bool binding;
    private bool saveReview;
    private bool cancelReview;

    public CommunicationCampaignForm()
    {
        InitializeComponent();
        sourceBox.SelectedIndex = 0;
    }

    internal CommunicationCampaignForm(DesktopDatabaseSettings settings) : this()
    {
        repository = new(settings);
        templates = new(settings);
    }

    private async void ReloadClicked(object? sender, EventArgs e) => await RunAsync(() => LoadAsync(selected?.Id));

    private async Task LoadAsync(int? id)
    {
        list = await repository!.ListCampaignsAsync(searchBox.Text);
        string templateNotice = "";
        if ((list.Create || list.Edit) && templates is not null)
        {
            try
            {
                var available = await templates.ListAsync("", false);
                templateBox.DisplayMember = nameof(EmailTemplateRow.Name);
                templateBox.DataSource = available.Rows;
                if (available.Rows.Count == 0)
                    templateNotice = " Create or enable an email template to prepare a campaign.";
            }
            catch (UnauthorizedAccessException)
            {
                templateBox.DataSource = null;
                templateNotice = " Template access is required to create or edit campaigns.";
            }
        }
        binding = true;
        campaignGrid.DataSource = list.Rows;
        if (id is int key)
            campaignGrid.CurrentRow = campaignGrid.Rows.FirstOrDefault(row => row.DataBoundItem is EmailCampaign campaign && campaign.Id == key);
        binding = false;
        SelectionChanged(null, EventArgs.Empty);
        feedback.Text = (list.Rows.Count == 0 ? "No email campaigns match the search." : $"Showing {list.Rows.Count} email campaign(s).") + templateNotice;
    }

    private void SelectionChanged(object? sender, EventArgs e)
    {
        if (binding)
            return;
        isNew = false;
        selected = campaignGrid.CurrentRow?.DataBoundItem as EmailCampaign;
        BindEditor();
    }

    private void NewClicked(object? sender, EventArgs e)
    {
        isNew = true;
        selected = null;
        BindEditor();
        nameBox.Focus();
    }

    private void BindEditor()
    {
        binding = true;
        nameBox.Text = selected?.Name ?? "";
        sourceBox.SelectedIndex = selected?.Source == "contact" ? 1 : 0;
        segmentBox.Text = selected?.SegmentStatus ?? "";
        limitBox.Value = selected?.Limit ?? 50;
        templateBox.SelectedItem = (templateBox.DataSource as List<EmailTemplateRow>)?.FirstOrDefault(row => row.Id == selected?.Template);
        audienceGrid.DataSource = null;
        sampleBox.Clear();
        feedback.Text = "";
        saveReview = cancelReview = false;
        binding = false;
        UpdateControls();
    }

    private void InputChanged(object? sender, EventArgs e)
    {
        if (binding)
            return;
        saveReview = cancelReview = false;
        audienceGrid.DataSource = null;
        sampleBox.Clear();
        feedback.Text = "";
        UpdateControls();
    }

    private async void SaveClicked(object? sender, EventArgs e)
    {
        if (!saveButton.Enabled || templateBox.SelectedItem is not EmailTemplateRow template)
            return;
        var draft = new CampaignInput(nameBox.Text.Trim(), template.Id, sourceBox.SelectedIndex == 1 ? "contact" : "lead",
            segmentBox.Text.Trim(), (int)limitBox.Value);
        if (!saveReview)
        {
            saveReview = true;
            cancelReview = false;
            feedback.Text = $"Review {draft.Name} with template {template.Name}, {draft.Source} audience and a maximum of {draft.Limit} recipients.";
            UpdateControls();
            return;
        }
        await RunAsync(async () =>
        {
            int id = await repository!.SaveCampaignAsync(selected, draft);
            await LoadAsync(id);
            feedback.Text = $"Campaign #{id} saved. Preview its audience below.";
        });
    }

    private async void CancelClicked(object? sender, EventArgs e)
    {
        if (!cancelButton.Enabled || selected is not { } campaign)
            return;
        if (!cancelReview)
        {
            cancelReview = true;
            saveReview = false;
            feedback.Text = $"Cancel {campaign.Name} (campaign #{campaign.Id})?";
            UpdateControls();
            return;
        }
        await RunAsync(async () =>
        {
            await repository!.CancelCampaignAsync(campaign);
            await LoadAsync(campaign.Id);
            feedback.Text = $"Campaign #{campaign.Id} cancelled.";
        });
    }

    private async void PreviewClicked(object? sender, EventArgs e)
    {
        if (!previewButton.Enabled || selected is not { } campaign)
            return;
        await RunAsync(async () =>
        {
            var audience = await repository!.PreviewCampaignAsync(campaign);
            audienceGrid.DataSource = audience.Rows;
            sampleBox.Text = audience.Subject.Length == 0 ? "" : audience.Subject + Environment.NewLine + Environment.NewLine + audience.Body;
            int included = audience.Rows.Count(row => row.Outcome == "Included");
            feedback.Text = $"{included} included, {audience.Rows.Count - included} excluded. Preview uses the saved campaign.";
        });
    }

    private void HistoryClicked(object? sender, EventArgs e)
    {
        if (repository is null || busy || selected is not { } campaign)
            return;
        using var history = new CommunicationCampaignHistoryForm(repository, campaign);
        history.ShowDialog(this);
    }

    private async Task RunAsync(Func<Task> action)
    {
        if (repository is null || busy)
            return;
        busy = true;
        UpdateControls();
        try { await action(); }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or ArgumentException or
            UnauthorizedAccessException or InvalidOperationException)
        {
            feedback.Text = error is NpgsqlException or TimeoutException
                ? "Could not verify the campaign action. Refresh the list before retrying." : error.Message;
            saveReview = cancelReview = false;
        }
        finally
        {
            busy = false;
            UpdateControls();
        }
    }

    private void UpdateControls()
    {
        bool edit = !busy && ((isNew && list?.Create == true) ||
            (!isNew && list?.Edit == true && selected?.State is "draft" or "cancelled"));
        refreshButton.Enabled = campaignGrid.Enabled = !busy;
        newButton.Enabled = !busy && list?.Create == true;
        nameBox.Enabled = templateBox.Enabled = sourceBox.Enabled = segmentBox.Enabled = limitBox.Enabled = edit;
        saveButton.Enabled = edit && nameBox.Text.Trim().Length >= 2 && templateBox.SelectedItem is EmailTemplateRow;
        previewButton.Enabled = !busy && selected is not null;
        historyButton.Enabled = previewButton.Enabled;
        cancelButton.Enabled = !busy && list?.Edit == true && selected?.State is "draft" or "scheduled";
        saveButton.Text = saveReview ? "Confirm and save" : "Review and save";
        cancelButton.Text = cancelReview ? "Confirm cancellation" : "Cancel campaign";
    }

    private void ClosingCampaigns(object? sender, FormClosingEventArgs e) => e.Cancel = busy;
}
