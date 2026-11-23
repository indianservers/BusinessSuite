namespace Business_Suite;

public sealed partial class LeadTeamNoteForm
{
    private void InitializeComponent()
    {
        this.bodyLabel = new Label();
        this.bodyBox = new TextBox();
        this.recipientsLabel = new Label();
        this.recipientsBox = new CheckedListBox();
        this.feedback = new Label();
        this.saveButton = new Button();
        this.cancelButton = new Button();
        this.SuspendLayout();
        this.bodyLabel.Location = new Point(18, 16);
        this.bodyLabel.Size = new Size(504, 25);
        this.bodyLabel.Text = "Team update";
        this.bodyBox.Name = "bodyBox";
        this.bodyBox.Location = new Point(18, 43);
        this.bodyBox.Size = new Size(504, 111);
        this.bodyBox.Multiline = true;
        this.bodyBox.ScrollBars = ScrollBars.Vertical;
        this.bodyBox.MaxLength = 4000;
        this.recipientsLabel.Location = new Point(18, 167);
        this.recipientsLabel.Size = new Size(504, 24);
        this.recipientsLabel.Text = "Notify teammates who can access this Lead";
        this.recipientsBox.Name = "recipientsBox";
        this.recipientsBox.Location = new Point(18, 194);
        this.recipientsBox.Size = new Size(504, 126);
        this.recipientsBox.CheckOnClick = true;
        this.recipientsBox.Enabled = false;
        this.feedback.Name = "feedback";
        this.feedback.Location = new Point(18, 327);
        this.feedback.Size = new Size(504, 35);
        this.saveButton.Name = "saveButton";
        this.saveButton.Location = new Point(267, 370);
        this.saveButton.Size = new Size(144, 34);
        this.saveButton.Text = "Post update";
        this.saveButton.Enabled = false;
        this.saveButton.Click += this.SaveClicked;
        this.cancelButton.Location = new Point(419, 370);
        this.cancelButton.Size = new Size(103, 34);
        this.cancelButton.Text = "Cancel";
        this.cancelButton.DialogResult = DialogResult.Cancel;
        this.Controls.AddRange(new Control[] { this.bodyLabel, this.bodyBox, this.recipientsLabel, this.recipientsBox,
            this.feedback, this.saveButton, this.cancelButton });
        this.AutoScaleMode = AutoScaleMode.Font;
        this.ClientSize = new Size(540, 422);
        this.FormBorderStyle = FormBorderStyle.FixedDialog;
        this.MaximizeBox = false;
        this.MinimizeBox = false;
        this.StartPosition = FormStartPosition.CenterParent;
        this.AcceptButton = this.saveButton;
        this.CancelButton = this.cancelButton;
        this.Text = "Post Lead team update";
        this.Shown += this.FormShown;
        this.FormClosed += this.FormIsClosed;
        this.ResumeLayout(false);
    }

    private Label bodyLabel;
    private TextBox bodyBox;
    private Label recipientsLabel;
    private CheckedListBox recipientsBox;
    private Label feedback;
    private Button saveButton;
    private Button cancelButton;
}
