#nullable disable
using System.Drawing;
using System.Windows.Forms;
using Telerik.WinControls.UI;

namespace Business_Suite
{
    partial class PmsProjectCloneForm
    {
        private void InitializeComponent()
        {
            this.nameLabel = new Label();
            this.keyLabel = new Label();
            this.nameInput = new RadTextBox();
            this.keyInput = new RadTextBox();
            this.tasksInput = new CheckBox();
            this.datesInput = new CheckBox();
            this.teamInput = new CheckBox();
            this.attachmentsInput = new CheckBox();
            this.milestonesInput = new CheckBox();
            this.dependenciesInput = new CheckBox();
            this.statusLabel = new Label();
            this.saveButton = new RadButton();
            this.closeButton = new RadButton();
            this.SuspendLayout();

            this.nameLabel.Name = "nameLabel";
            this.nameLabel.Text = "New project name";
            this.nameLabel.Location = new Point(14, 15);
            this.nameLabel.Size = new Size(175, 25);
            this.nameInput.Name = "nameInput";
            this.nameInput.Location = new Point(14, 40);
            this.nameInput.Size = new Size(435, 25);
            this.nameInput.MaxLength = 180;

            this.keyLabel.Name = "keyLabel";
            this.keyLabel.Text = "Unique project key";
            this.keyLabel.Location = new Point(14, 78);
            this.keyLabel.Size = new Size(175, 25);
            this.keyInput.Name = "keyInput";
            this.keyInput.Location = new Point(14, 103);
            this.keyInput.Size = new Size(435, 25);
            this.keyInput.CharacterCasing = CharacterCasing.Upper;
            this.keyInput.MaxLength = 20;

            this.tasksInput.Name = "tasksInput";
            this.tasksInput.Text = "Tasks and checklists";
            this.tasksInput.Location = new Point(14, 150);
            this.tasksInput.Size = new Size(435, 25);
            this.tasksInput.Checked = true;

            this.datesInput.Name = "datesInput";
            this.datesInput.Text = "Keep original dates";
            this.datesInput.Location = new Point(14, 177);
            this.datesInput.Size = new Size(435, 25);
            this.datesInput.Checked = false;

            this.teamInput.Name = "teamInput";
            this.teamInput.Text = "Members and task assignees";
            this.teamInput.Location = new Point(14, 204);
            this.teamInput.Size = new Size(435, 25);
            this.teamInput.Checked = false;

            this.attachmentsInput.Name = "attachmentsInput";
            this.attachmentsInput.Text = "Attachments using the original stored files";
            this.attachmentsInput.Location = new Point(14, 231);
            this.attachmentsInput.Size = new Size(435, 25);
            this.attachmentsInput.Checked = false;

            this.milestonesInput.Name = "milestonesInput";
            this.milestonesInput.Text = "Milestones";
            this.milestonesInput.Location = new Point(14, 258);
            this.milestonesInput.Size = new Size(435, 25);
            this.milestonesInput.Checked = true;

            this.dependenciesInput.Name = "dependenciesInput";
            this.dependenciesInput.Text = "Dependencies between copied tasks";
            this.dependenciesInput.Location = new Point(14, 285);
            this.dependenciesInput.Size = new Size(435, 25);
            this.dependenciesInput.Checked = true;
            this.tasksInput.CheckedChanged += this.TasksChanged;

            this.statusLabel.Name = "statusLabel";
            this.statusLabel.Location = new Point(14, 325);
            this.statusLabel.Size = new Size(435, 54);

            this.saveButton.Name = "saveButton";
            this.saveButton.Text = "Duplicate project";
            this.saveButton.Location = new Point(220, 394);
            this.saveButton.Size = new Size(134, 29);
            this.saveButton.Click += this.SaveClicked;

            this.closeButton.Name = "closeButton";
            this.closeButton.Text = "Cancel";
            this.closeButton.Location = new Point(365, 394);
            this.closeButton.Size = new Size(84, 29);
            this.closeButton.DialogResult = DialogResult.Cancel;

            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.ClientSize = new Size(464, 437);
            this.Controls.AddRange(new Control[] {
                this.nameLabel, this.nameInput, this.keyLabel, this.keyInput,
                this.tasksInput, this.datesInput, this.teamInput, this.attachmentsInput, this.milestonesInput, this.dependenciesInput,
                this.statusLabel, this.saveButton, this.closeButton });
            this.Font = new Font("Segoe UI", 10F);
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.MaximizeBox = false;
            this.MinimizeBox = false;
            this.Name = "PmsProjectCloneForm";
            this.StartPosition = FormStartPosition.CenterParent;
            this.Text = "Duplicate project";
            this.AcceptButton = this.saveButton;
            this.CancelButton = this.closeButton;
            this.ResumeLayout(false);
            this.PerformLayout();
        }

        private Label nameLabel;
        private Label keyLabel;
        private RadTextBox nameInput;
        private RadTextBox keyInput;
        private CheckBox tasksInput;
        private CheckBox datesInput;
        private CheckBox teamInput;
        private CheckBox attachmentsInput;
        private CheckBox milestonesInput;
        private CheckBox dependenciesInput;
        private Label statusLabel;
        private RadButton saveButton;
        private RadButton closeButton;
    }
}
