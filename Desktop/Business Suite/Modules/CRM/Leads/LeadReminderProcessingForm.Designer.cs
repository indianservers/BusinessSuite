namespace Business_Suite;

public sealed partial class LeadReminderProcessingForm
{
    private void InitializeComponent()
    {
        this.scopeLabel = new Label();
        this.details = new Label();
        this.feedback = new Label();
        this.processButton = new Button();
        this.slaButton = new Button();
        this.salesButton = new Button();
        this.setupButton = new Button();
        this.routingButton = new Button();
        this.closeButton = new Button();
        this.SuspendLayout();
        this.scopeLabel.Name = "scopeLabel";
        this.scopeLabel.Location = new Point(18, 14);
        this.scopeLabel.Size = new Size(480, 26);
        this.scopeLabel.Font = new Font("Segoe UI Semibold", 11F);
        this.details.Location = new Point(18, 51);
        this.details.Size = new Size(480, 52);
        this.details.Text = "Process overdue first responses, due follow-ups, or configured sales process alerts.";
        this.feedback.Name = "feedback";
        this.feedback.Location = new Point(18, 107);
        this.feedback.Size = new Size(480, 40);
        this.processButton.Name = "processButton";
        this.processButton.Location = new Point(208, 157);
        this.processButton.Size = new Size(177, 35);
        this.processButton.Text = "Process due follow-ups";
        this.processButton.Enabled = false;
        this.processButton.Click += this.ProcessClicked;
        this.slaButton.Name = "slaButton";
        this.slaButton.Location = new Point(18, 157);
        this.slaButton.Size = new Size(178, 35);
        this.slaButton.Text = "Process first-response alerts";
        this.slaButton.Enabled = false;
        this.slaButton.Click += this.SlaClicked;
        this.salesButton.Name = "salesButton";
        this.salesButton.Location = new Point(18, 202);
        this.salesButton.Size = new Size(178, 35);
        this.salesButton.Text = "Process sales process alerts";
        this.salesButton.Enabled = false;
        this.salesButton.Click += this.SalesClicked;
        this.setupButton.Name = "setupButton";
        this.setupButton.Location = new Point(208, 202);
        this.setupButton.Size = new Size(177, 35);
        this.setupButton.Text = "Sales process settings";
        this.setupButton.Click += this.SetupClicked;
        this.routingButton.Name = "routingButton";
        this.routingButton.Location = new Point(18, 247);
        this.routingButton.Size = new Size(178, 35);
        this.routingButton.Text = "Lead routing settings";
        this.routingButton.Click += this.RoutingClicked;
        this.closeButton.Name = "closeButton";
        this.closeButton.Location = new Point(394, 247);
        this.closeButton.Size = new Size(104, 35);
        this.closeButton.Text = "Close";
        this.closeButton.DialogResult = DialogResult.Cancel;
        this.Controls.AddRange(new Control[] { this.scopeLabel, this.details, this.feedback, this.slaButton,
            this.processButton, this.salesButton, this.setupButton, this.routingButton, this.closeButton });
        this.AutoScaleMode = AutoScaleMode.Font;
        this.ClientSize = new Size(516, 301);
        this.FormBorderStyle = FormBorderStyle.FixedDialog;
        this.MaximizeBox = false;
        this.MinimizeBox = false;
        this.StartPosition = FormStartPosition.CenterParent;
        this.CancelButton = this.closeButton;
        this.Text = "Lead reminders";
        this.Shown += this.FormShown;
        this.FormClosed += this.FormIsClosed;
        this.ResumeLayout(false);
    }

    private Label scopeLabel;
    private Label details;
    private Label feedback;
    private Button processButton;
    private Button slaButton;
    private Button salesButton;
    private Button setupButton;
    private Button routingButton;
    private Button closeButton;
}
