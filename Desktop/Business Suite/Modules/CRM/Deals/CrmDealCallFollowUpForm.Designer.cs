namespace Business_Suite;

public sealed partial class CrmDealCallFollowUpForm
{
    private Label titleLabel;
    private Label dueLabel;
    private TextBox titleBox;
    private DateTimePicker dueBox;
    private Label feedback;
    private Button saveButton;
    private Button cancelButton;

    private void InitializeComponent()
    {
        this.titleLabel = new Label();
        this.dueLabel = new Label();
        this.titleBox = new TextBox();
        this.dueBox = new DateTimePicker();
        this.feedback = new Label();
        this.saveButton = new Button();
        this.cancelButton = new Button();
        this.SuspendLayout();

        this.titleLabel.Name = "titleLabel";
        this.titleLabel.Text = "Title";
        this.titleLabel.Location = new Point(18, 18);
        this.titleLabel.Size = new Size(104, 24);
        this.titleBox.Name = "titleBox";
        this.titleBox.Location = new Point(130, 17);
        this.titleBox.Size = new Size(362, 27);
        this.titleBox.MaxLength = 220;
        this.dueLabel.Name = "dueLabel";
        this.dueLabel.Text = "Due (local time)";
        this.dueLabel.Location = new Point(18, 65);
        this.dueLabel.Size = new Size(111, 24);
        this.dueBox.Name = "dueBox";
        this.dueBox.Location = new Point(130, 63);
        this.dueBox.Size = new Size(362, 27);
        this.dueBox.Format = DateTimePickerFormat.Custom;
        this.dueBox.CustomFormat = "dd MMM yyyy HH:mm";
        this.dueBox.ShowCheckBox = true;
        this.dueBox.Checked = false;
        this.feedback.Name = "feedback";
        this.feedback.Location = new Point(18, 110);
        this.feedback.Size = new Size(474, 50);
        this.feedback.Text = "The task is assigned to you and retains the linked CRM records.";
        this.saveButton.Name = "saveButton";
        this.saveButton.Text = "Save follow-up";
        this.saveButton.Location = new Point(250, 169);
        this.saveButton.Size = new Size(130, 34);
        this.saveButton.Click += this.SaveClicked;
        this.cancelButton.Name = "cancelButton";
        this.cancelButton.Text = "Cancel";
        this.cancelButton.Location = new Point(388, 169);
        this.cancelButton.Size = new Size(104, 34);
        this.cancelButton.DialogResult = DialogResult.Cancel;
        this.Controls.Add(this.titleLabel);
        this.Controls.Add(this.titleBox);
        this.Controls.Add(this.dueLabel);
        this.Controls.Add(this.dueBox);
        this.Controls.Add(this.feedback);
        this.Controls.Add(this.saveButton);
        this.Controls.Add(this.cancelButton);
        this.AcceptButton = this.saveButton;
        this.CancelButton = this.cancelButton;
        this.ClientSize = new Size(510, 220);
        this.AutoScaleDimensions = new SizeF(96F, 96F);
        this.AutoScaleMode = AutoScaleMode.Dpi;
        this.Font = new Font("Segoe UI", 10F);
        this.FormBorderStyle = FormBorderStyle.FixedDialog;
        this.MaximizeBox = false;
        this.MinimizeBox = false;
        this.StartPosition = FormStartPosition.CenterParent;
        this.Text = "Create a follow-up task";
        this.FormClosing += this.FormIsClosing;
        this.FormClosed += this.FormIsClosed;
        this.ResumeLayout(false);
        this.PerformLayout();
    }
}
