namespace Business_Suite;

public sealed partial class CrmDealNoteForm
{
    private Label bodyLabel;
    private TextBox bodyBox;
    private Label feedback;
    private Label mentionLabel;
    private Telerik.WinControls.UI.RadDropDownList mentionBox;
    private Button mentionButton;
    private Button saveButton;
    private Button cancelButton;

    private void InitializeComponent()
    {
        this.bodyLabel = new Label();
        this.bodyBox = new TextBox();
        this.feedback = new Label();
        this.mentionLabel = new Label();
        this.mentionBox = new Telerik.WinControls.UI.RadDropDownList();
        this.mentionButton = new Button();
        this.saveButton = new Button();
        this.cancelButton = new Button();
        this.SuspendLayout();

        this.bodyLabel.Name = "bodyLabel";
        this.bodyLabel.Text = "Internal note";
        this.bodyLabel.Location = new Point(18, 16);
        this.bodyLabel.Size = new Size(510, 23);
        this.bodyBox.Name = "bodyBox";
        this.bodyBox.AccessibleName = "Internal note";
        this.bodyBox.Location = new Point(18, 45);
        this.bodyBox.Size = new Size(510, 215);
        this.bodyBox.Multiline = true;
        this.bodyBox.AcceptsReturn = true;
        this.bodyBox.ScrollBars = ScrollBars.Vertical;
        this.bodyBox.MaxLength = 10000;
        this.feedback.Name = "feedback";
        this.mentionLabel.Name = "mentionLabel";
        this.mentionLabel.Text = "Mention teammate";
        this.mentionLabel.Location = new Point(18, 272);
        this.mentionLabel.Size = new Size(510, 22);
        this.mentionBox.Name = "mentionBox";
        this.mentionBox.Location = new Point(18, 296);
        this.mentionBox.Size = new Size(386, 30);
        this.mentionBox.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
        this.mentionBox.Enabled = false;
        this.mentionButton.Name = "mentionButton";
        this.mentionButton.Text = "Insert mention";
        this.mentionButton.Location = new Point(413, 295);
        this.mentionButton.Size = new Size(115, 32);
        this.mentionButton.Enabled = false;
        this.mentionButton.Click += this.InsertMentionClicked;
        this.feedback.Location = new Point(18, 337);
        this.feedback.Size = new Size(510, 45);
        this.saveButton.Name = "saveButton";
        this.saveButton.Text = "Save note";
        this.saveButton.Location = new Point(316, 385);
        this.saveButton.Size = new Size(102, 34);
        this.saveButton.Click += this.SaveClicked;
        this.cancelButton.Name = "cancelButton";
        this.cancelButton.Text = "Cancel";
        this.cancelButton.Location = new Point(426, 385);
        this.cancelButton.Size = new Size(102, 34);
        this.cancelButton.DialogResult = DialogResult.Cancel;
        this.Controls.Add(this.bodyLabel);
        this.Controls.Add(this.bodyBox);
        this.Controls.Add(this.mentionLabel);
        this.Controls.Add(this.mentionBox);
        this.Controls.Add(this.mentionButton);
        this.Controls.Add(this.feedback);
        this.Controls.Add(this.saveButton);
        this.Controls.Add(this.cancelButton);
        this.CancelButton = this.cancelButton;
        this.ClientSize = new Size(550, 437);
        this.AutoScaleDimensions = new SizeF(96F, 96F);
        this.AutoScaleMode = AutoScaleMode.Dpi;
        this.Font = new Font("Segoe UI", 10F);
        this.FormBorderStyle = FormBorderStyle.FixedDialog;
        this.MaximizeBox = false;
        this.MinimizeBox = false;
        this.StartPosition = FormStartPosition.CenterParent;
        this.Text = "Add Deal note";
        this.Shown += this.NoteShown;
        this.FormClosing += this.NoteIsClosing;
        this.FormClosed += this.NoteIsClosed;
        this.ResumeLayout(false);
        this.PerformLayout();
    }
}
