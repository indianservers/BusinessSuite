using Npgsql;
using System.Security.Cryptography;

namespace Business_Suite;

public sealed partial class CommunicationDraftForm : Form
{
    private readonly CommunicationDraftRepository? drafts;
    private bool busy;
    private bool saving;
    private IReadOnlyDictionary<string, string> mergeValues = new Dictionary<string, string>();
    private ProtectedAppointmentJournal<CommunicationWorkingDraft>? localDraft;
    private FileStream? draftLease;
    private DraftRecipientReference? recipientReference;
    private bool localWritable;
    private bool restoring;
    private bool localDirty;
    private bool checkingOptOut;
    private int optOutRevision;

    internal int DraftId { get; private set; }

    public CommunicationDraftForm()
    {
        InitializeComponent();
    }

    private async void ComposerShown(object? sender, EventArgs e)
    {
        if (drafts is null)
            return;
        CommunicationWorkingDraft? saved;
        try
        {
            localDraft = drafts.WorkingDraftJournal();
            draftLease = localDraft.Acquire();
            saved = localDraft.Read();
            localWritable = true;
            localLabel.Text = saved is null ? "Working draft is saved on this PC as you type." : "Restored the working draft from this PC.";
        }
        catch (Exception error) when (IsLocalDraftError(error))
        {
            localLabel.Text = "Local autosave is unavailable for this window.";
            clearButton.Enabled = draftLease is not null;
            return;
        }
        if (saved is null)
        {
            DraftChanged(sender, e);
            return;
        }
        restoring = true;
        SetBusy(true);
        try
        {
            subjectBox.Text = saved.Subject;
            bodyBox.Text = saved.Body;
            mergeValues = saved.MergeValues;
            recipientReference = saved.Recipient;
            emailBox.Text = saved.Email;
            if (saved.Recipient is { } reference)
            {
                DraftRecipient? recipient = await drafts.RestoreRecipientAsync(reference);
                if (IsDisposed)
                    return;
                if (recipient is null)
                    statusLabel.Text = "Choose a current CRM recipient before saving to Business Suite.";
                else
                {
                    recipientList.DisplayMember = nameof(DraftRecipient.Display);
                    recipientList.DataSource = new[] { recipient };
                    recipientList.SelectedIndex = 0;
                }
            }
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException or InvalidOperationException)
        {
            if (!IsDisposed)
                statusLabel.Text = "The local message was restored. Use Find to verify the CRM recipient before saving.";
        }
        finally
        {
            restoring = false;
            SetBusy(false);
        }
    }

    internal CommunicationDraftForm(CommunicationDraftRepository drafts, EmailTemplateEdit? template) : this()
    {
        this.drafts = drafts;
        subjectBox.Text = template?.Row.Subject ?? "";
        bodyBox.Text = template?.Body ?? "";
    }

    private async void FindClicked(object sender, EventArgs e)
    {
        if (drafts is null || busy)
            return;
        SetBusy(true);
        statusLabel.Text = "Searching CRM records…";
        try
        {
            var recipients = await drafts.SearchRecipientsAsync(searchBox.Text.Trim());
            if (IsDisposed)
                return;
            recipientList.DisplayMember = nameof(DraftRecipient.Display);
            recipientList.DataSource = recipients;
            statusLabel.Text = recipients.Count == 0 ? "No CRM recipients match the search." : "";
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

    private void RecipientChanged(object sender, Telerik.WinControls.UI.Data.PositionChangedEventArgs e)
    {
        if (!restoring)
        {
            var selected = recipientList.SelectedItem?.DataBoundItem as DraftRecipient;
            recipientReference = selected is null ? null : new(selected.Id, selected.Kind);
            emailBox.Text = selected?.Email ?? "";
            DraftChanged(sender, EventArgs.Empty);
        }
        saveButton.Enabled = !busy && recipientList.SelectedItem?.DataBoundItem is DraftRecipient;
        mergeButton.Enabled = saveButton.Enabled;
        ResetOptOut();
    }

    private void EmailChanged(object? sender, EventArgs e)
    {
        DraftChanged(sender, e);
        ResetOptOut();
    }

    private void ResetOptOut()
    {
        optOutRevision++;
        optOutLabel.Text = "";
        UpdateOptOutButton();
    }

    private void UpdateOptOutButton()
    {
        bool selected = !busy && !string.IsNullOrWhiteSpace(emailBox.Text) &&
            recipientList.SelectedItem?.DataBoundItem is DraftRecipient;
        optOutButton.Enabled = selected && !checkingOptOut;
        consentButton.Enabled = selected;
    }

    private void ConsentClicked(object? sender, EventArgs e)
    {
        if (drafts is null || !consentButton.Enabled || recipientList.SelectedItem?.DataBoundItem is not DraftRecipient recipient)
            return;
        using var history = new CommunicationEmailConsentForm(drafts, new(recipient.Id, recipient.Kind), emailBox.Text);
        history.ShowDialog(this);
        ResetOptOut();
    }

    private async void CheckOptOutClicked(object? sender, EventArgs e)
    {
        if (drafts is null || !optOutButton.Enabled || recipientList.SelectedItem?.DataBoundItem is not DraftRecipient recipient)
            return;
        int revision = optOutRevision;
        checkingOptOut = true;
        UpdateOptOutButton();
        optOutLabel.Text = "Checking recorded email opt-out…";
        try
        {
            bool? blocked = await drafts.EmailOptOutAsync(new(recipient.Id, recipient.Kind), emailBox.Text);
            if (!IsDisposed && revision == optOutRevision)
                optOutLabel.Text = blocked switch
                {
                    true => "This address has opted out of email. You can still save a draft.",
                    false => "No email opt-out was recorded for this address.",
                    _ => "Confirm this address on a CRM record visible in the selected branch."
                };
        }
        catch (ArgumentException error)
        {
            if (!IsDisposed && revision == optOutRevision)
                optOutLabel.Text = error.Message;
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException or InvalidOperationException)
        {
            if (!IsDisposed && revision == optOutRevision)
                optOutLabel.Text = "Could not verify email opt-out. Check PostgreSQL connectivity and access.";
        }
        finally
        {
            checkingOptOut = false;
            if (!IsDisposed)
                UpdateOptOutButton();
        }
    }

    private void MergeClicked(object sender, EventArgs e)
    {
        if (busy || recipientList.SelectedItem?.DataBoundItem is not DraftRecipient recipient)
            return;
        using var dialog = new CommunicationMergePreviewForm(recipient, emailBox.Text, subjectBox.Text, bodyBox.Text, mergeValues);
        if (dialog.ShowDialog(this) == DialogResult.OK)
        {
            mergeValues = dialog.Values;
            DraftChanged(sender, EventArgs.Empty);
        }
    }

    private void BodyKeyDown(object? sender, KeyEventArgs e)
    {
        if (!busy && drafts is not null && bodyBox.Text.Length == 0 &&
            (e.KeyCode is Keys.OemQuestion or Keys.Divide) && e.Modifiers == Keys.None)
        {
            e.SuppressKeyPress = true;
            QuickRepliesClicked(this, EventArgs.Empty);
        }
    }

    private void QuickRepliesClicked(object? sender, EventArgs e)
    {
        if (drafts is null || busy)
            return;
        using var dialog = new CommunicationQuickRepliesForm(drafts.QuickReplyStore());
        if (dialog.ShowDialog(this) != DialogResult.OK || dialog.InsertedText is not string reply)
            return;
        string message = bodyBox.Text.Length == 0 ? reply : bodyBox.Text + Environment.NewLine + Environment.NewLine + reply;
        if (message.Length > 50000)
        {
            statusLabel.Text = "This reply would exceed the 50,000-character message limit.";
            return;
        }
        bodyBox.Text = message;
    }

    private async void SaveClicked(object sender, EventArgs e)
    {
        if (drafts is null || busy || recipientList.SelectedItem?.DataBoundItem is not DraftRecipient recipient)
            return;
        string email = emailBox.Text;
        string subject = subjectBox.Text;
        string body = bodyBox.Text;
        SetBusy(true);
        saving = true;
        statusLabel.Text = "Saving email draft…";
        try
        {
            DraftId = await drafts.SaveAsync(recipient, email, subject, body, mergeValues);
            DialogResult = DialogResult.OK;
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException or
            InvalidOperationException or ArgumentException)
        {
            statusLabel.Text = ErrorMessage(error);
        }
        finally
        {
            saving = false;
            SetBusy(false);
        }
    }

    private void SetBusy(bool value)
    {
        busy = value;
        if (IsDisposed)
            return;
        searchButton.Enabled = cancelButton.Enabled = recipientList.Enabled = !value;
        saveButton.Enabled = !value && recipientList.SelectedItem?.DataBoundItem is DraftRecipient;
        mergeButton.Enabled = saveButton.Enabled;
        quickRepliesButton.Enabled = !value;
        clearButton.Enabled = !value;
        emailBox.ReadOnly = subjectBox.ReadOnly = bodyBox.ReadOnly = value;
        UpdateOptOutButton();
    }

    private void DraftChanged(object? sender, EventArgs e)
    {
        if (!localWritable || restoring)
            return;
        localDirty = true;
        autosaveTimer.Stop();
        autosaveTimer.Start();
    }

    private void AutosaveTick(object? sender, EventArgs e) => FlushLocalDraft();

    private void FlushLocalDraft()
    {
        autosaveTimer.Stop();
        if (!localWritable || !localDirty || localDraft is null)
            return;
        try
        {
            var current = new CommunicationWorkingDraft(recipientReference, emailBox.Text, subjectBox.Text, bodyBox.Text,
                mergeValues.ToDictionary(pair => pair.Key, pair => pair.Value));
            if (current.Recipient is null && current.Email.Length == 0 && current.Subject.Length == 0 && current.Body.Length == 0)
            {
                localDraft.Clear();
                localLabel.Text = "Working draft is saved on this PC as you type.";
            }
            else
            {
                localDraft.Save(current);
                localLabel.Text = $"Working draft saved on this PC at {DateTime.Now:t}.";
            }
            localDirty = false;
        }
        catch (Exception error) when (IsLocalDraftError(error))
        {
            localLabel.Text = "The working draft could not be saved on this PC.";
        }
    }

    private void ClearDraftClicked(object? sender, EventArgs e)
    {
        if (busy)
            return;
        try
        {
            if (draftLease is not null)
            {
                localDraft!.Clear();
                localWritable = true;
            }
            restoring = true;
            recipientReference = null;
            recipientList.DataSource = null;
            searchBox.Clear();
            emailBox.Clear();
            subjectBox.Clear();
            bodyBox.Clear();
            mergeValues = new Dictionary<string, string>();
            localDirty = false;
            autosaveTimer.Stop();
            statusLabel.Text = "";
            localLabel.Text = draftLease is null ? "The editor was cleared. Local autosave is unavailable."
                : "The local working draft was cleared.";
        }
        catch (Exception error) when (IsLocalDraftError(error))
        {
            localLabel.Text = "The saved working draft could not be cleared.";
        }
        finally
        {
            restoring = false;
        }
    }

    private void EditorClosing(object sender, FormClosingEventArgs e)
    {
        if (saving && DialogResult != DialogResult.OK)
        {
            e.Cancel = true;
            return;
        }
        FlushLocalDraft();
    }

    private void EditorClosed(object? sender, FormClosedEventArgs e)
    {
        localWritable = false;
        autosaveTimer.Dispose();
        draftLease?.Dispose();
    }

    private static bool IsLocalDraftError(Exception error) => error is IOException or UnauthorizedAccessException or
        ArgumentException or InvalidOperationException or CryptographicException;

    private static string ErrorMessage(Exception error) => error is NpgsqlException or TimeoutException
        ? "Could not complete the draft action. Check database connectivity and access."
        : error.Message;
}
