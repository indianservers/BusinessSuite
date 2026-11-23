using Npgsql;

namespace Business_Suite;

public sealed partial class EmailTemplateForm : Form
{
    private readonly CommunicationTemplatesRepository? templates;
    private readonly EmailTemplateEdit? original;
    private bool saving;

    public EmailTemplateForm()
    {
        InitializeComponent();
    }

    internal EmailTemplateForm(CommunicationTemplatesRepository templates, EmailTemplateEdit? original, bool editable) : this()
    {
        this.templates = templates;
        this.original = original;
        Text = original is null ? "New email template" : editable ? "Edit email template" : "View email template";
        nameBox.Text = original?.Row.Name ?? "";
        subjectBox.Text = original?.Row.Subject ?? "";
        bodyBox.Text = original?.Body ?? "";
        nameBox.ReadOnly = subjectBox.ReadOnly = bodyBox.ReadOnly = !editable;
        saveButton.Visible = editable;
        if (!editable)
            cancelButton.Text = "Close";
        if (editable && original?.Row.Active == false)
            saveButton.Text = "Save and enable";
    }

    private async void SaveClicked(object sender, EventArgs e)
    {
        if (templates is null || saving)
            return;
        saving = true;
        saveButton.Enabled = false;
        cancelButton.Enabled = false;
        statusLabel.Text = "Saving…";
        try
        {
            await templates.SaveAsync(original, nameBox.Text, subjectBox.Text, bodyBox.Text);
            DialogResult = DialogResult.OK;
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or ArgumentException or
            UnauthorizedAccessException or InvalidOperationException)
        {
            statusLabel.Text = error is NpgsqlException or TimeoutException
                ? "Could not confirm saving. Refresh the template list before repeating the action."
                : error.Message;
        }
        finally
        {
            saving = false;
            if (!IsDisposed)
            {
                saveButton.Enabled = true;
                cancelButton.Enabled = true;
            }
        }
    }

    private void EditorClosing(object sender, FormClosingEventArgs e)
    {
        if (saving && DialogResult != DialogResult.OK)
            e.Cancel = true;
    }
}
