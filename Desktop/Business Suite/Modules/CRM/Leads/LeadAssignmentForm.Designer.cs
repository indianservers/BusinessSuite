#nullable disable
namespace Business_Suite;

public sealed partial class LeadAssignmentForm
{
    private Label ownerLabel;
    private ComboBox ownerBox;
    private Label reasonLabel;
    private TextBox reasonBox;
    private Label feedback;
    private Button saveButton;
    private Button closeButton;

    private void InitializeComponent()
    {
        this.ownerLabel = new Label();
        this.ownerBox = new ComboBox();
        this.reasonLabel = new Label();
        this.reasonBox = new TextBox();
        this.feedback = new Label();
        this.saveButton = new Button();
        this.closeButton = new Button();
        this.SuspendLayout();
        this.ownerLabel.Location = new Point(16, 14);
        this.ownerLabel.Size = new Size(484, 23);
        this.ownerLabel.Text = "Lead owner";
        this.ownerBox.Name = "ownerBox";
        this.ownerBox.Location = new Point(16, 42);
        this.ownerBox.Size = new Size(484, 27);
        this.ownerBox.DisplayMember = "Name";
        this.ownerBox.DropDownStyle = ComboBoxStyle.DropDownList;
        this.ownerBox.Enabled = false;
        this.reasonLabel.Location = new Point(16, 83);
        this.reasonLabel.Size = new Size(484, 23);
        this.reasonLabel.Text = "Reassignment reason (optional)";
        this.reasonBox.Name = "reasonBox";
        this.reasonBox.Location = new Point(16, 110);
        this.reasonBox.Size = new Size(484, 92);
        this.reasonBox.Multiline = true;
        this.reasonBox.MaxLength = 1000;
        this.reasonBox.ScrollBars = ScrollBars.Vertical;
        this.reasonBox.Enabled = false;
        this.feedback.Name = "feedback";
        this.feedback.Location = new Point(16, 216);
        this.feedback.Size = new Size(484, 47);
        this.feedback.Text = "Loading eligible Lead owners…";
        this.saveButton.Name = "saveButton";
        this.saveButton.Location = new Point(298, 270);
        this.saveButton.Size = new Size(107, 33);
        this.saveButton.Text = "Save owner";
        this.saveButton.Enabled = false;
        this.saveButton.Click += this.SaveClicked;
        this.closeButton.Location = new Point(415, 270);
        this.closeButton.Size = new Size(85, 33);
        this.closeButton.Text = "Cancel";
        this.closeButton.DialogResult = DialogResult.Cancel;
        this.Controls.AddRange(new Control[] {this.ownerLabel,this.ownerBox,this.reasonLabel,this.reasonBox,
            this.feedback,this.saveButton,this.closeButton});
        this.Name = "LeadAssignmentForm";
        this.Text = "Assign Lead owner";
        this.ClientSize = new Size(516, 320);
        this.AutoScaleMode = AutoScaleMode.Font;
        this.FormBorderStyle = FormBorderStyle.FixedDialog;
        this.StartPosition = FormStartPosition.CenterParent;
        this.MaximizeBox = false;
        this.MinimizeBox = false;
        this.CancelButton = this.closeButton;
        this.Shown += this.FormShown;
        this.FormClosing += this.ClosingHandler;
        this.FormClosed += this.ClosedHandler;
        this.ResumeLayout(false);
    }
}
