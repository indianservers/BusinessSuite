namespace Business_Suite;

public sealed partial class LeadNurtureConsentForm
{
    private void InitializeComponent()
    {
        this.heading = new Label();
        this.allowedBox = new CheckBox();
        this.evidenceLabel = new Label();
        this.evidenceBox = new TextBox();
        this.feedback = new Label();
        this.saveButton = new Button();
        this.cancelButton = new Button();
        this.SuspendLayout();
        this.heading.Name = "heading";
        this.heading.Location = new Point(18, 14);
        this.heading.Size = new Size(479, 27);
        this.heading.AutoEllipsis = true;
        this.heading.Font = new Font("Segoe UI Semibold", 12F);
        this.heading.Text = "Lead";
        this.allowedBox.Name = "allowedBox";
        this.allowedBox.Location = new Point(18, 48);
        this.allowedBox.Size = new Size(479, 27);
        this.allowedBox.Text = "Permission to receive nurture follow-ups";
        this.evidenceLabel.Location = new Point(18, 82);
        this.evidenceLabel.Size = new Size(479, 24);
        this.evidenceLabel.Text = "Permission evidence or withdrawal reason";
        this.evidenceBox.Name = "evidenceBox";
        this.evidenceBox.Location = new Point(18, 110);
        this.evidenceBox.Size = new Size(479, 120);
        this.evidenceBox.MaxLength = 1000;
        this.evidenceBox.Multiline = true;
        this.evidenceBox.ScrollBars = ScrollBars.Vertical;
        this.feedback.Name = "feedback";
        this.feedback.Location = new Point(18, 238);
        this.feedback.Size = new Size(479, 44);
        this.saveButton.Name = "saveButton";
        this.saveButton.Location = new Point(267, 288);
        this.saveButton.Size = new Size(122, 35);
        this.saveButton.Text = "Record permission";
        this.saveButton.Click += this.SaveClicked;
        this.cancelButton.Location = new Point(397, 288);
        this.cancelButton.Size = new Size(100, 35);
        this.cancelButton.Text = "Cancel";
        this.cancelButton.DialogResult = DialogResult.Cancel;
        this.Controls.AddRange(new Control[] { this.heading, this.allowedBox, this.evidenceLabel,
            this.evidenceBox, this.feedback, this.saveButton, this.cancelButton });
        this.AutoScaleMode = AutoScaleMode.Font;
        this.ClientSize = new Size(515, 339);
        this.FormBorderStyle = FormBorderStyle.FixedDialog;
        this.MaximizeBox = false;
        this.MinimizeBox = false;
        this.StartPosition = FormStartPosition.CenterParent;
        this.AcceptButton = this.saveButton;
        this.CancelButton = this.cancelButton;
        this.Text = "Lead nurture permission";
        this.FormClosed += this.FormIsClosed;
        this.ResumeLayout(false);
        this.PerformLayout();
    }

    private Label heading;
    private CheckBox allowedBox;
    private Label evidenceLabel;
    private TextBox evidenceBox;
    private Label feedback;
    private Button saveButton;
    private Button cancelButton;
}
