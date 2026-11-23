using System.ComponentModel;

namespace Business_Suite;

public partial class CommunicationWebformsForm : Form
{
    private readonly CommunicationDraftRepository? repository;
    private readonly BindingList<WebformFieldInput> fields = [];
    private bool busy, canCreate, reviewing, fieldsChanged;
    private WebformRow? publicationReview;
    private WebformEdit? original;

    public CommunicationWebformsForm() => InitializeComponent();

    internal CommunicationWebformsForm(DesktopDatabaseSettings settings) : this()
    {
        repository = new(settings);
        fieldsGrid.DataSource = fields;
        ResetFields();
        fieldsChanged = false;
        UpdateControls();
    }

    private async void RefreshClicked(object? sender, EventArgs e)
    {
        InputChanged(null, EventArgs.Empty);
        await LoadAsync();
    }

    private async Task LoadAsync(string? saved = null)
    {
        if (busy || repository is null) return;
        busy = true;
        UpdateControls();
        try
        {
            var library = await repository.WebformsAsync(searchBox.Text);
            libraryGrid.DataSource = library.Forms;
            canCreate = library.CanCreate;
            int previous = ruleBox.SelectedValue is int id ? id : 0;
            ruleBox.DataSource = library.Rules;
            ruleBox.SelectedValue = library.Rules.Any(rule => rule.Id == previous) ? previous : 0;
            feedback.Text = saved ?? (library.Forms.Count == 0 ? "No matching webforms." : "");
        }
        catch (Exception error)
        {
            canCreate = false;
            libraryGrid.DataSource = null;
            feedback.Text = error is UnauthorizedAccessException ? error.Message : "Could not load customer webforms.";
        }
        finally
        {
            busy = false;
            UpdateControls();
        }
    }

    private async void SaveClicked(object? sender, EventArgs e)
    {
        if (busy || (original is null && !canCreate) || repository is null) return;
        fieldsGrid.EndEdit();
        string name = nameBox.Text.Trim();
        string slug = slugBox.Text.Trim();
        string target = targetBox.SelectedItem?.Value as string ?? "";
        int rule = ruleBox.SelectedValue is int id ? id : 0;
        try
        {
            CommunicationDraftRepository.ValidateWebform(name, slug, target, fields.ToList());
            if (!reviewing)
            {
                InputChanged(null, EventArgs.Empty);
                reviewing = true;
                saveButton.Text = "Confirm save";
                string status = original?.Active == true ? "active" : "inactive";
                feedback.Text = $"Save {name} as an {status} {target} form at {slug} with {fields.Count} mapped field(s). "
                    + $"Acknowledgement: {ruleBox.SelectedItem?.Text}.";
                if (original?.Active == true)
                    feedback.Text += " Changes take effect immediately on a connected public server."
                        + (original.Slug == slug ? "" : " The previous URL will stop working.");
                return;
            }
            busy = true;
            UpdateControls();
            int saved;
            if (original is null)
                saved = await repository.CreateWebformAsync(name, slug, target, rule, fields.ToList());
            else
            {
                saved = original.Id;
                await repository.UpdateWebformAsync(original, name, slug, target, rule, fields.ToList());
            }
            string savedStatus = original?.Active == true ? "active" : "inactive";
            ResetEditor();
            busy = false;
            await LoadAsync($"Saved {savedStatus} webform #{saved}.");
        }
        catch (Exception error)
        {
            InputChanged(null, EventArgs.Empty);
            feedback.Text = error is ArgumentException or InvalidOperationException or UnauthorizedAccessException
                ? error.Message : "Could not save the webform.";
        }
        finally
        {
            busy = false;
            UpdateControls();
        }
    }

    private async void EditClicked(object? sender, EventArgs e)
    {
        if (busy || repository is null) return;
        if (original is not null)
        {
            ResetEditor();
            await LoadAsync();
            return;
        }
        if (libraryGrid.CurrentRow?.DataBoundItem is not WebformRow { CanEdit:true } row) return;
        // Keep an unsaved new draft intact while opening saved configurations.
        if (nameBox.TextLength > 0 || slugBox.TextLength > 0 || targetBox.SelectedIndex > 0 || ruleBox.SelectedIndex > 0 || fieldsChanged)
        {
            feedback.Text = "Save or clear the new draft before opening an existing draft.";
            return;
        }
        busy = true;
        UpdateControls();
        try
        {
            original = await repository.EditWebformAsync(row.Id, row.Revision);
            nameBox.Text = original.Name;
            slugBox.Text = original.Slug;
            targetBox.SelectedValue = original.Target;
            ruleBox.DataSource = original.Rules;
            ruleBox.SelectedValue = original.Rule;
            fields.Clear();
            foreach (var field in original.Fields) fields.Add(field);
            InputChanged(null, EventArgs.Empty);
            feedback.Text = $"Editing {(original.Active ? "active" : "inactive")} webform #{original.Id}.";
        }
        catch (Exception error)
        {
            feedback.Text = error is UnauthorizedAccessException or InvalidOperationException
                ? error.Message : "Could not open the saved webform for editing.";
        }
        finally
        {
            busy = false;
            UpdateControls();
        }
    }

    private async void ClearDraftClicked(object? sender, EventArgs e)
    {
        if (busy || original is not null) return;
        ResetEditor();
        await LoadAsync();
    }

    private void ResetEditor()
    {
        original = null;
        nameBox.Clear();
        slugBox.Clear();
        targetBox.SelectedIndex = 0;
        ruleBox.SelectedValue = 0;
        ResetFields();
        fieldsChanged = false;
        InputChanged(null, EventArgs.Empty);
    }

    private void FieldsChanged(object? sender, EventArgs e)
    {
        fieldsChanged = true;
        InputChanged(sender, e);
        UpdateControls();
    }

    private async void DetailsClicked(object? sender, EventArgs e)
    {
        if (busy || repository is null || libraryGrid.CurrentRow?.DataBoundItem is not WebformRow row) return;
        InputChanged(null, EventArgs.Empty);
        busy = true;
        UpdateControls();
        try
        {
            var detail = await repository.OpenWebformAsync(row.Id);
            using var dialog = new CommunicationWebformDetailsForm(detail);
            dialog.ShowDialog(this);
        }
        catch (Exception error)
        {
            feedback.Text = error is UnauthorizedAccessException or InvalidOperationException
                ? error.Message : "Could not open the saved webform configuration.";
        }
        finally
        {
            busy = false;
            UpdateControls();
        }
    }

    private async void PublicationClicked(object? sender, EventArgs e)
    {
        if (busy || repository is null ||
            libraryGrid.CurrentRow?.DataBoundItem is not WebformRow row || !CanChangePublication(row)) return;
        if (publicationReview != row)
        {
            InputChanged(null, EventArgs.Empty);
            publicationReview = row;
            publicationButton.Text = row.Active ? "Confirm stop" : "Confirm";
            feedback.Text = row.Active
                ? $"Deactivate {row.Name} ({row.Slug})? The connected public form will stop accepting submissions. "
                + "Its definition and submission history will be retained."
                : $"Activate {row.Name} ({row.Slug})? A connected public server can then display the form and accept submissions.";
            return;
        }
        busy = true;
        UpdateControls();
        try
        {
            if (row.Active) await repository.DeactivateWebformAsync(row.Id, row.Revision);
            else await repository.ActivateWebformAsync(row.Id, row.Revision);
            publicationReview = null;
            publicationButton.Text = "Deactivate...";
            busy = false;
            await LoadAsync($"{(row.Active ? "Deactivated" : "Activated")} {row.Name}.");
        }
        catch (Exception error)
        {
            InputChanged(null, EventArgs.Empty);
            feedback.Text = error is InvalidOperationException or UnauthorizedAccessException
                ? error.Message : "Could not change the webform activation state.";
        }
        finally
        {
            busy = false;
            UpdateControls();
        }
    }

    private void SelectionChanged(object? sender, EventArgs e)
    {
        if (publicationReview is not null) InputChanged(null, EventArgs.Empty);
        UpdateControls();
    }

    private void ClosingWebforms(object? sender, FormClosingEventArgs e) => e.Cancel = busy;

    private void AddClicked(object? sender, EventArgs e)
    {
        fields.Add(new());
        fieldsChanged = true;
        InputChanged(null, EventArgs.Empty);
        UpdateControls();
    }

    private void RemoveClicked(object? sender, EventArgs e)
    {
        if (fieldsGrid.CurrentRow?.DataBoundItem is WebformFieldInput field)
        {
            fields.Remove(field);
            fieldsChanged = true;
        }
        InputChanged(null, EventArgs.Empty);
        UpdateControls();
    }

    private void ResetFields()
    {
        fields.Clear();
        fields.Add(new() { Key="first_name", Label="First name", Target="first_name", Required=true });
        fields.Add(new() { Key="email", Label="Email", Type="email", Target="email", Required=true });
    }

    private void InputChanged(object? sender, EventArgs e)
    {
        reviewing = false;
        publicationReview = null;
        publicationButton.Text = libraryGrid.CurrentRow?.DataBoundItem is WebformRow { Active:true } ? "Deactivate..." : "Activate...";
        saveButton.Text = "Review configuration";
        feedback.Text = "";
    }

    private static bool CanChangePublication(WebformRow row) => row.Active ? row.CanDeactivate : row.CanEdit;

    private void UpdateControls()
    {
        bool edit = !busy && (canCreate || original is not null);
        refreshButton.Enabled = !busy && original is null;
        clearButton.Enabled = !busy && canCreate && original is null;
        editButton.Text = original is null ? "Edit form" : "Cancel edit";
        editButton.Enabled = !busy && (original is not null || libraryGrid.CurrentRow?.DataBoundItem is WebformRow { CanEdit:true });
        detailsButton.Enabled = !busy && original is null && libraryGrid.CurrentRow?.DataBoundItem is WebformRow;
        var selectedForm = libraryGrid.CurrentRow?.DataBoundItem as WebformRow;
        publicationButton.Enabled = !busy && original is null && selectedForm is not null && CanChangePublication(selectedForm);
        if (publicationReview is null)
            publicationButton.Text = selectedForm?.Active == true ? "Deactivate..." : "Activate...";
        nameBox.Enabled = slugBox.Enabled = targetBox.Enabled = ruleBox.Enabled = edit;
        fieldsGrid.Enabled = addButton.Enabled = saveButton.Enabled = edit;
        removeButton.Enabled = edit && fields.Count > 0;
    }
}
