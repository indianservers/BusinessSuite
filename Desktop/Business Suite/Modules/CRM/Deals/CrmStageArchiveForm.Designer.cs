using Telerik.WinControls.UI;

namespace Business_Suite;

public sealed partial class CrmStageArchiveForm
{
    private Label prompt;
    private Label targetLabel;
    private RadDropDownList targetBox;
    private Button archiveButton;
    private Button cancelButton;

    private void InitializeComponent()
    {
        this.prompt = new Label();
        this.targetLabel = new Label();
        this.targetBox = new RadDropDownList();
        this.archiveButton = new Button();
        this.cancelButton = new Button();
        this.SuspendLayout();
        this.prompt.Name = "prompt";
        this.prompt.Location = new Point(18, 17);
        this.prompt.Size = new Size(497, 72);
        this.targetLabel.Name = "targetLabel";
        this.targetLabel.Text = "Replacement stage";
        this.targetLabel.Location = new Point(18, 96);
        this.targetLabel.Size = new Size(170, 26);
        this.targetBox.Name = "targetBox";
        this.targetBox.Location = new Point(184, 93);
        this.targetBox.Size = new Size(331, 30);
        this.targetBox.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
        this.targetBox.SelectedIndexChanged += this.SelectionChanged;
        this.archiveButton.Name = "archiveButton";
        this.archiveButton.Text = "Archive";
        this.archiveButton.Location = new Point(294, 153);
        this.archiveButton.Size = new Size(108, 34);
        this.archiveButton.Enabled = false;
        this.archiveButton.Click += this.ArchiveClicked;
        this.cancelButton.Name = "cancelButton";
        this.cancelButton.Text = "Cancel";
        this.cancelButton.Location = new Point(410, 153);
        this.cancelButton.Size = new Size(105, 34);
        this.cancelButton.DialogResult = DialogResult.Cancel;
        this.Controls.Add(this.prompt);
        this.Controls.Add(this.targetLabel);
        this.Controls.Add(this.targetBox);
        this.Controls.Add(this.archiveButton);
        this.Controls.Add(this.cancelButton);
        this.CancelButton = this.cancelButton;
        this.ClientSize = new Size(533, 207);
        this.AutoScaleDimensions = new SizeF(96F, 96F);
        this.AutoScaleMode = AutoScaleMode.Dpi;
        this.Font = new Font("Segoe UI", 10F);
        this.StartPosition = FormStartPosition.CenterParent;
        this.FormBorderStyle = FormBorderStyle.FixedDialog;
        this.MaximizeBox = false;
        this.MinimizeBox = false;
        this.Text = "Archive pipeline stage";
        this.ResumeLayout(false);
    }
}
