namespace Business_Suite;

internal sealed partial class EmployeeAttachmentUploadForm : Form
{
    private readonly EmployeeAdministrationRepository? repository;
    private readonly CancellationTokenSource lifetime = new();
    private readonly int employee;
    private readonly string? revision;
    private bool saving;

    public EmployeeAttachmentUploadForm() => InitializeComponent();

    internal EmployeeAttachmentUploadForm(EmployeeAdministrationRepository repository, int employee, string revision) : this()
    {
        this.repository = repository;
        this.employee = employee;
        this.revision = revision;
    }

    internal int AddedDocument { get; private set; }

    private void BrowseClicked(object? sender, EventArgs e)
    {
        if (sourceDialog.ShowDialog(this) != DialogResult.OK)
            return;
        source.Text = sourceDialog.FileName;
        upload.Enabled = true;
    }

    private async void UploadClicked(object? sender, EventArgs e)
    {
        if (repository is null || revision is null || saving)
            return;
        saving = true;
        upload.Enabled = browse.Enabled = close.Enabled = false;
        status.Text = "Saving document to local storage…";
        try
        {
            AddedDocument = await repository.UploadEmployeeAttachmentAsync(employee, revision, kind.Text, documentName.Text,
                expiry.Checked ? expiry.Value.Date : (DateTime?)null, source.Text, lifetime.Token);
        }
        catch (Exception error) when (error is UnauthorizedAccessException or InvalidOperationException
            or IOException or Npgsql.NpgsqlException or TimeoutException)
        {
            status.Text = error is UnauthorizedAccessException or InvalidOperationException ? error.Message
                : "Could not upload the document. Check PostgreSQL and the local storage folder.";
        }
        finally
        {
            saving = false;
            upload.Enabled = browse.Enabled = close.Enabled = true;
        }
        if (AddedDocument > 0)
            DialogResult = DialogResult.OK;
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
