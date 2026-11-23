using Npgsql;

namespace Business_Suite;

public sealed partial class EmailTemplateTimelineForm : Form
{
    private readonly CommunicationTemplatesRepository? templates;
    private readonly EmailTemplateRow? template;

    public EmailTemplateTimelineForm()
    {
        InitializeComponent();
    }

    internal EmailTemplateTimelineForm(CommunicationTemplatesRepository templates, EmailTemplateRow template) : this()
    {
        this.templates = templates;
        this.template = template;
        Text = $"Template history | {template.Name}";
    }

    private async void RefreshClicked(object sender, EventArgs e)
    {
        if (templates is null || template is null || !refreshButton.Enabled)
            return;
        refreshButton.Enabled = false;
        timelineGrid.DataSource = null;
        statusLabel.Text = "Loading history…";
        try
        {
            var events = await templates.TimelineAsync(template.Id);
            if (!IsDisposed)
            {
                timelineGrid.DataSource = events;
                statusLabel.Text = events.Count == 0 ? "No template history to show." : "";
            }
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or
            UnauthorizedAccessException or InvalidOperationException)
        {
            if (!IsDisposed)
                statusLabel.Text = error is UnauthorizedAccessException or InvalidOperationException ? error.Message
                    : "Could not load template history. Check database connectivity and access, then refresh.";
        }
        finally
        {
            if (!IsDisposed)
                refreshButton.Enabled = true;
        }
    }
}
