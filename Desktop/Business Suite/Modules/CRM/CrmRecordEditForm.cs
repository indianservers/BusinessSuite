using System.Data;
using Npgsql;

namespace Business_Suite;

public sealed partial class CrmRecordEditForm : Form
{
    private readonly CrmDirectoryKind kind;
    private readonly CrmRecordKey? recordKey;
    private readonly int? linkedCompanyId;
    private readonly CancellationTokenSource lifetime = new();
    private CrmExtras? extras;
    private bool choicesReady;
    private bool saving;

    public CrmRecordEditForm() : this(CrmDirectoryKind.Companies, null) { }

    internal CrmRecordEditForm(CrmDirectoryKind kind, DataRowView? record, string? defaultRole = null)
    {
        this.kind = kind;
        recordKey = record is null ? null : CrmDirectoryForm.GetKey(record);
        linkedCompanyId = record?["company_id"] as int?;
        InitializeComponent();
        saveButton.Enabled = false;
        extrasButton.Enabled = false;
        duplicateReasonBox.Visible = duplicateReasonLabel.Visible = false;
        bool company = kind == CrmDirectoryKind.Companies;
        headingLabel.Text = $"{(record is null ? "New" : "Edit")} {(company ? "company" : "contact")}";
        Text = $"Business Suite | {headingLabel.Text}";
        lastNameBox.Visible = lastNameLabel.Visible = companyBox.Visible = companyLabel.Visible = !company;
        industryBox.Visible = industryLabel.Visible = company;
        branchBox.Visible = branchLabel.Visible = recordKey is null;
        if (!company)
        {
            nameLabel.Text = nameBox.AccessibleName = "First name";
            nameBox.MaxLength = 100;
            detailLabel.Text = detailBox.AccessibleName = "Job title";
            detailBox.MaxLength = 120;
            classificationLabel.Text = classificationBox.AccessibleName = "Lifecycle stage";
        }

        nameBox.Text = Read(company ? "name" : "first_name");
        lastNameBox.Text = Read("last_name");
        detailBox.Text = Read("detail_name");
        industryBox.Text = company ? Read("context") : "";
        emailBox.Text = Read("email");
        phoneBox.Text = Read("phone");
        phoneCodeBox.Items.AddRange(CrmPhone.CallingCodes);
        phoneCodeBox.Text = record is null ? CrmPhone.DefaultCallingCode : Read("phone_country_code");
        websiteBox.Text = Read("website");
        addressBox.Text = Read("address");
        cityBox.Text = Read("city");
        stateBox.Text = Read("state");
        countryBox.Text = Read("country");
        tagsBox.Text = Read("tags");
        notesBox.Text = Read("notes");
        classificationBox.Text = Read("classification");
        if (classificationBox.Text.Length == 0)
            classificationBox.Text = company && defaultRole is "Customer" or "Vendor" or "Prospect" or "Partner"
                ? defaultRole : company ? "Prospect" : "Lead";
        statusBox.Text = Read("status");
        if (statusBox.Text.Length == 0)
            statusBox.Text = "Active";

        string Read(string key) => Convert.ToString(record?[key]) ?? "";
    }

    private async void LoadChoices(object sender, EventArgs e)
    {
        CancellationToken cancellation = lifetime.Token;
        try
        {
            var choices = await CrmDirectoryWrites.ReadEditorChoicesAsync(CrmDirectoryWrites.PermissionEntity(kind),
                recordKey is null, cancellation);
            extras = await CrmExtrasStore.LoadAsync(kind, recordKey?.Id, cancellation);
            if (cancellation.IsCancellationRequested)
                return;

            if (recordKey is null && choices.Branches.Count == 0)
            {
                saveStatus.Text = "Create or restore an active branch before adding CRM records.";
                return;
            }

            branchBox.DisplayMember = nameof(CrmLookup.Name);
            branchBox.DataSource = choices.Branches;
            int defaultBranch = choices.Branches.FindIndex(branch => branch.Id == choices.DefaultBranch);
            branchBox.SelectedIndex = defaultBranch >= 0 ? defaultBranch : choices.Branches.Count == 1 ? 0 : -1;

            if (linkedCompanyId.HasValue && !choices.Companies.Any(company => company.Id == linkedCompanyId))
                choices.Companies.Add(new(linkedCompanyId, $"Unavailable company #{linkedCompanyId}"));
            companyBox.DisplayMember = nameof(CrmLookup.Name);
            companyBox.DataSource = choices.Companies;
            companyBox.SelectedIndex = choices.Companies.FindIndex(company => company.Id == linkedCompanyId);
            RefreshChannelFields();
            extrasButton.Enabled = true;
            choicesReady = saveButton.Enabled = true;
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested) { }
        catch (Exception error) when (error is ArgumentException or InvalidOperationException or NpgsqlException or IOException
            or UnauthorizedAccessException or TimeoutException)
        {
            if (!cancellation.IsCancellationRequested)
                saveStatus.Text = error is InvalidOperationException or ArgumentException or UnauthorizedAccessException ? error.Message
                    : "Could not load branches or companies. Check the local database.";
        }
    }

    private void ExtrasClicked(object sender, EventArgs e)
    {
        if (saving || extras is null)
            return;
        using var form = new CrmExtrasForm(extras, kind, emailBox.Text, phoneBox.Text, phoneCodeBox.Text);
        if (form.ShowDialog(this) != DialogResult.OK)
            return;

        extras = form.Result;
        RefreshChannelFields();
        IdentityChanged(sender, e);
    }

    private void RefreshChannelFields()
    {
        if (extras is null)
            return;
        emailBox.ReadOnly = extras.ChannelsEdited || extras.Channels.Any(item => item.Kind == "email");
        phoneBox.ReadOnly = extras.ChannelsEdited || extras.Channels.Any(item => item.Kind == "phone");
        phoneCodeBox.Enabled = !phoneBox.ReadOnly;
        if (extras.ChannelsEdited)
        {
            emailBox.Text = extras.Channels.FirstOrDefault(item => item.Kind == "email" && item.Primary)?.Value ?? "";
            var phone = extras.Channels.FirstOrDefault(item => item.Kind == "phone" && item.Primary);
            phoneBox.Text = phone?.Value ?? "";
            phoneCodeBox.Text = phone?.CountryCode ?? "";
        }
    }

    private async void SaveClicked(object sender, EventArgs e)
    {
        if (saving || !choicesReady)
            return;

        try
        {
            int? companyId = kind == CrmDirectoryKind.Contacts ? (companyBox.SelectedItem as CrmLookup)?.Id : null;
            int? branchId = (branchBox.SelectedItem as CrmLookup)?.Id;
            if (recordKey is null && !branchId.HasValue)
                throw new ArgumentException("Choose a branch.");

            var draft = new CrmRecordDraft(nameBox.Text.Trim(), lastNameBox.Text.Trim(), detailBox.Text.Trim(),
                industryBox.Text.Trim(), emailBox.Text.Trim(), phoneBox.Text.Trim(), phoneCodeBox.Text.Trim(),
                websiteBox.Text.Trim(), addressBox.Text.Trim(), cityBox.Text.Trim(), stateBox.Text.Trim(),
                countryBox.Text.Trim(), statusBox.Text.Trim(), classificationBox.Text.Trim(), tagsBox.Text.Trim(),
                notesBox.Text.Trim(), companyId, branchId);

            saving = true;
            saveButton.Enabled = cancelButton.Enabled = false;
            extrasButton.Enabled = false;
            saveStatus.Text = "Saving to local PostgreSQL…";
            string? duplicateReason = duplicateReasonBox.Visible ? duplicateReasonBox.Text.Trim() : null;
            await CrmDirectoryWrites.SaveAsync(kind, recordKey, draft, CancellationToken.None, duplicateReason, extras);
            saving = false;
            DialogResult = DialogResult.OK;
            Close();
        }
        catch (CrmDuplicateException error)
        {
            saveStatus.Text = error.Message;
            duplicateReasonBox.Visible = duplicateReasonLabel.Visible = true;
            saveButton.Text = "Save as separate";
            duplicateReasonBox.Focus();
        }
        catch (Exception error) when (error is ArgumentException or InvalidOperationException)
        {
            saveStatus.Text = error.Message;
        }
        catch (PostgresException error) when (error.SqlState == "40001" || error.SqlState == "40P01")
        {
            saveStatus.Text = "A concurrent save changed the record. Reopen the editor before retrying.";
        }
        catch (Exception error) when (error is NpgsqlException or IOException or UnauthorizedAccessException or TimeoutException)
        {
            saveStatus.Text = "Could not save the record. Check the local database and try again.";
        }
        finally
        {
            saving = false;
            if (!IsDisposed)
            {
                saveButton.Enabled = cancelButton.Enabled = true;
                extrasButton.Enabled = true;
            }
        }
    }

    private void IdentityChanged(object sender, EventArgs e)
    {
        duplicateReasonBox.Clear();
        duplicateReasonBox.Visible = duplicateReasonLabel.Visible = false;
        saveButton.Text = "Save";
    }

    private void EditorClosing(object sender, FormClosingEventArgs e)
    {
        if (saving)
            e.Cancel = true;
    }

    private void EditorClosed(object sender, FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
}
