using Npgsql;

namespace Business_Suite;

public sealed partial class DocumentsAndCommunicationForm : Form
{
    private readonly CommunicationTemplatesRepository? templates;
    private readonly CommunicationDraftRepository? drafts;
    private readonly CommunicationDeliveryRepository? delivery;
    private readonly CommunicationCustomerRepository? customers;
    private readonly CommunicationTemplateFavorites? favorites;
    private readonly DesktopDatabaseSettings? settings;
    private EmailTemplateList? current;
    private bool busy;

    public DocumentsAndCommunicationForm()
    {
        InitializeComponent();
    }

    internal DocumentsAndCommunicationForm(DesktopDatabaseSettings settings) : this()
    {
        this.settings = settings;
        templates = new CommunicationTemplatesRepository(settings);
        drafts = new CommunicationDraftRepository(settings);
        delivery = new CommunicationDeliveryRepository(settings);
        customers = new CommunicationCustomerRepository(settings);
        favorites = new CommunicationTemplateFavorites(settings);
    }

    private void CampaignsClicked(object? sender, EventArgs e)
    {
        if (settings is null || busy)
            return;
        using var campaigns = new CommunicationCampaignForm(settings);
        campaigns.ShowDialog(this);
    }

    private void AutoResponsesClicked(object? sender, EventArgs e)
    {
        if (settings is null || busy)
            return;
        using var rules = new CommunicationAutoResponseRulesForm(settings);
        rules.ShowDialog(this);
    }

    private void WebformsClicked(object? sender, EventArgs e)
    {
        if (settings is null || busy)
            return;
        using var webforms = new CommunicationWebformsForm(settings);
        webforms.ShowDialog(this);
    }

    private async void RefreshClicked(object sender, EventArgs e) => await LoadTemplatesAsync();

    private async Task LoadTemplatesAsync()
    {
        if (templates is null || busy)
            return;
        SetBusy(true);
        current = null;
        templateGrid.DataSource = null;
        statusLabel.Text = "Loading templates…";
        try
        {
            string warning = "";
            HashSet<int>? favoriteIds = null;
            try
            {
                favoriteIds = favorites?.Load().Ids;
            }
            catch (Exception error) when (IsFavoriteStorageError(error))
            {
                warning = "Local favorites could not be loaded. ";
            }
            current = await templates.ListAsync(searchBox.Text.Trim(), disabledCheck.Checked,
                favoriteIds, favoritesOnlyCheck.Checked);
            if (IsDisposed)
                return;
            templateGrid.DataSource = current.Rows;
            statusLabel.Text = warning + (current.Rows.Count == 0 ? "No templates match the filters."
                : current.Rows.Count == 200 ? "Showing the latest 200 matching templates. Refine search for older records."
                : $"{current.Rows.Count} {(current.Rows.Count == 1 ? "template" : "templates")}");
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException)
        {
            if (!IsDisposed)
                statusLabel.Text = ErrorMessage(error);
        }
        finally
        {
            SetBusy(false);
        }
    }

    private async void FavoriteClicked(object sender, EventArgs e)
    {
        if (favorites is null || SelectedTemplate() is not { } selected || busy)
            return;
        try
        {
            favorites.Toggle(selected.Id);
        }
        catch (Exception error) when (IsFavoriteStorageError(error))
        {
            statusLabel.Text = "Could not update your local template favorites.";
            return;
        }
        await LoadTemplatesAsync();
        if (IsDisposed)
            return;
        var row = templateGrid.Rows.FirstOrDefault(candidate =>
            candidate.DataBoundItem is EmailTemplateRow template && template.Id == selected.Id);
        if (row is not null)
            templateGrid.CurrentRow = row;
    }

    private async void NewClicked(object sender, EventArgs e)
    {
        if (templates is null || current?.Create != true)
            return;
        using var editor = new EmailTemplateForm(templates, null, true);
        if (editor.ShowDialog(this) == DialogResult.OK)
            await LoadTemplatesAsync();
    }

    private async void OpenClicked(object sender, EventArgs e)
    {
        if (templates is null || SelectedTemplate() is not { } selected || busy)
            return;
        SetBusy(true);
        bool refresh = false;
        try
        {
            var template = await templates.OpenAsync(selected.Id);
            if (IsDisposed)
                return;
            using var editor = new EmailTemplateForm(templates, template, current?.Edit == true);
            refresh = editor.ShowDialog(this) == DialogResult.OK;
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException or InvalidOperationException)
        {
            if (!IsDisposed)
                statusLabel.Text = ErrorMessage(error);
        }
        finally
        {
            SetBusy(false);
        }
        if (refresh)
            await LoadTemplatesAsync();
    }

    private async void DisableClicked(object sender, EventArgs e)
    {
        if (templates is null || SelectedTemplate() is not { Active: true } selected || busy)
            return;
        SetBusy(true);
        bool refresh = false;
        try
        {
            var template = await templates.OpenAsync(selected.Id);
            await templates.DisableAsync(template);
            refresh = true;
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException or InvalidOperationException)
        {
            if (!IsDisposed)
                statusLabel.Text = ErrorMessage(error);
        }
        finally
        {
            SetBusy(false);
        }
        if (refresh)
            await LoadTemplatesAsync();
    }

    private void HistoryClicked(object sender, EventArgs e)
    {
        if (templates is null || SelectedTemplate() is not { } selected)
            return;
        using var history = new EmailTemplateTimelineForm(templates, selected);
        history.ShowDialog(this);
    }

    private async void ComposeClicked(object sender, EventArgs e)
    {
        if (templates is null || drafts is null || busy)
            return;
        SetBusy(true);
        try
        {
            var selected = SelectedTemplate();
            EmailTemplateEdit? template = selected?.Active == true ? await templates.OpenAsync(selected.Id) : null;
            if (IsDisposed)
                return;
            using var composer = new CommunicationDraftForm(drafts, template);
            if (composer.ShowDialog(this) == DialogResult.OK)
                statusLabel.Text = $"Email draft #{composer.DraftId} saved.";
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException or InvalidOperationException)
        {
            if (!IsDisposed)
                statusLabel.Text = ErrorMessage(error);
        }
        finally
        {
            SetBusy(false);
        }
    }

    private void DraftsClicked(object sender, EventArgs e)
    {
        if (drafts is null || busy)
            return;
        using var draftList = new CommunicationDraftListForm(drafts);
        draftList.ShowDialog(this);
    }

    private void DeliveryClicked(object sender, EventArgs e)
    {
        if (delivery is null || busy)
            return;
        using var history = new CommunicationDeliveryForm(delivery);
        history.ShowDialog(this);
    }

    private void CustomersClicked(object sender, EventArgs e)
    {
        if (customers is null || busy)
            return;
        using var workspace = new CommunicationCustomerForm(customers);
        workspace.ShowDialog(this);
    }

    private EmailTemplateRow? SelectedTemplate() => templateGrid.CurrentRow?.DataBoundItem as EmailTemplateRow;

    private void SelectionChanged(object sender, EventArgs e) => UpdateButtons();

    private void SetBusy(bool value)
    {
        busy = value;
        if (IsDisposed)
            return;
        refreshButton.Enabled = !busy;
        disabledCheck.Enabled = !busy;
        favoritesOnlyCheck.Enabled = !busy && favorites is not null;
        UpdateButtons();
    }

    private void UpdateButtons()
    {
        newButton.Enabled = !busy && current?.Create == true;
        openButton.Enabled = !busy && SelectedTemplate() is not null;
        disableButton.Enabled = !busy && current?.Disable == true && SelectedTemplate()?.Active == true;
        historyButton.Enabled = !busy && SelectedTemplate() is not null;
        favoriteButton.Enabled = !busy && favorites is not null && SelectedTemplate() is not null;
        favoriteButton.Text = SelectedTemplate()?.Favorite == true ? "Remove favorite" : "Favorite template";
        composeButton.Enabled = !busy && drafts is not null;
        draftsButton.Enabled = !busy && drafts is not null;
        deliveryButton.Enabled = !busy && delivery is not null;
        customersButton.Enabled = !busy && customers is not null;
        campaignsButton.Enabled = !busy && settings is not null;
        autoResponsesButton.Enabled = !busy && settings is not null;
        webformsButton.Enabled = !busy && settings is not null;
    }

    private static bool IsFavoriteStorageError(Exception error) => error is IOException or TimeoutException or
        UnauthorizedAccessException or ArgumentException or InvalidOperationException;

    private static string ErrorMessage(Exception error) => error is NpgsqlException or TimeoutException
        ? "Could not complete the template action. Check database connectivity and access, then refresh."
        : error.Message;
}
