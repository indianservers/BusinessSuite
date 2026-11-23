using System.Data;

namespace Business_Suite;

public sealed partial class CommunicationMergePreviewForm : Form
{
    private readonly DraftRecipient? recipient;
    private readonly string email = "";
    private readonly string subject = "";
    private readonly string body = "";
    private readonly DataTable fields = new();

    public CommunicationMergePreviewForm() => InitializeComponent();

    internal CommunicationMergePreviewForm(DraftRecipient recipient, string email, string subject, string body,
        IReadOnlyDictionary<string, string> previous) : this()
    {
        this.recipient = recipient;
        this.email = email.Trim().ToLowerInvariant();
        this.subject = subject;
        this.body = body;
        var names = CommunicationDraftRepository.CustomMergeFields(subject, body);
        fields.Columns.Add("Field", typeof(string));
        fields.Columns.Add("Value", typeof(string));
        foreach (string field in names)
            fields.Rows.Add(field, previous.TryGetValue(field, out string value) ? value : "");
        grid.DataSource = fields;
        RefreshPreview();
    }

    internal IReadOnlyDictionary<string, string> Values { get; private set; } = new Dictionary<string, string>();

    private Dictionary<string, string> ReadValues() => fields.Rows.Cast<DataRow>()
        .ToDictionary(row => (string)row["Field"], row => row.Field<string>("Value") ?? "", StringComparer.Ordinal);

    private void PreviewChanged(object? sender, EventArgs e) => RefreshPreview();

    private void RefreshPreview()
    {
        if (recipient is null)
            return;
        var values = ReadValues();
        string renderedSubject = CommunicationDraftRepository.Render(subject.Trim(), recipient, email, values);
        string renderedBody = CommunicationDraftRepository.Render(body, recipient, email, values);
        previewBox.Text = $"To: {email}{Environment.NewLine}Subject: {renderedSubject}{Environment.NewLine}{Environment.NewLine}{renderedBody}";
        int missing = values.Values.Count(string.IsNullOrWhiteSpace);
        feedback.Text = missing switch
        {
            0 => "Values are ready to use in the draft.",
            1 => "Enter a value for the remaining template field.",
            _ => $"Enter values for the remaining {missing} template fields."
        };
    }

    private void AcceptClicked(object? sender, EventArgs e)
    {
        grid.EndEdit();
        Values = ReadValues();
        DialogResult = DialogResult.OK;
        Close();
    }
}
