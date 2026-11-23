namespace Business_Suite;

public sealed partial class LeadScoreBatchForm
{
    private void InitializeComponent()
    {
        this.scopeLabel = new Label();
        this.details = new Label();
        this.feedback = new Label();
        this.calculateButton = new Button();
        this.manageRulesButton = new Button();
        this.closeButton = new Button();
        this.SuspendLayout();
        this.scopeLabel.Name = "scopeLabel";
        this.scopeLabel.Location = new Point(18, 14);
        this.scopeLabel.Size = new Size(480, 26);
        this.scopeLabel.Font = new Font("Segoe UI Semibold", 11F);
        this.details.Location = new Point(18, 51);
        this.details.Size = new Size(480, 40);
        this.details.Text = "Recalculate automatic scores for active Leads and Potential Clients in this scope. Manual overrides are retained.";
        this.feedback.Name = "feedback";
        this.feedback.Location = new Point(18, 105);
        this.feedback.Size = new Size(480, 42);
        this.calculateButton.Name = "calculateButton";
        this.calculateButton.Location = new Point(201, 157);
        this.calculateButton.Size = new Size(183, 35);
        this.calculateButton.Text = "Recalculate automatic scores";
        this.calculateButton.Enabled = false;
        this.calculateButton.Click += this.CalculateClicked;
        this.manageRulesButton.Name = "manageRulesButton";
        this.manageRulesButton.Location = new Point(18, 157);
        this.manageRulesButton.Size = new Size(137, 35);
        this.manageRulesButton.Text = "Manage rules";
        this.manageRulesButton.Click += this.ManageRulesClicked;
        this.closeButton.Name = "closeButton";
        this.closeButton.Location = new Point(394, 157);
        this.closeButton.Size = new Size(104, 35);
        this.closeButton.Text = "Close";
        this.closeButton.DialogResult = DialogResult.Cancel;
        this.Controls.AddRange(new Control[] { this.scopeLabel, this.details, this.feedback, this.manageRulesButton,
            this.calculateButton, this.closeButton });
        this.AutoScaleMode = AutoScaleMode.Font;
        this.ClientSize = new Size(516, 211);
        this.FormBorderStyle = FormBorderStyle.FixedDialog;
        this.MaximizeBox = false;
        this.MinimizeBox = false;
        this.StartPosition = FormStartPosition.CenterParent;
        this.CancelButton = this.closeButton;
        this.Text = "Recalculate automatic Lead scores";
        this.Shown += this.FormShown;
        this.FormClosed += this.FormIsClosed;
        this.ResumeLayout(false);
    }

    private Label scopeLabel;
    private Label details;
    private Label feedback;
    private Button calculateButton;
    private Button manageRulesButton;
    private Button closeButton;
}
