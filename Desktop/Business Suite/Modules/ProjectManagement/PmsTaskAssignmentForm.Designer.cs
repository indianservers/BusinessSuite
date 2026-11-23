#nullable disable
using System.Drawing;
using System.Windows.Forms;
using Telerik.WinControls.UI;

namespace Business_Suite
{
    partial class PmsTaskAssignmentForm
    {
        private void InitializeComponent()
        {
            this.heading = new Label();
            this.peopleList = new CheckedListBox();
            this.noteLabel = new Label();
            this.noteInput = new RadTextBox();
            this.notifyInput = new CheckBox();
            this.statusLabel = new Label();
            this.saveButton = new RadButton();
            this.cancelButton = new RadButton();
            this.SuspendLayout();

            this.heading.Name = "heading";
            this.heading.Location = new Point(14, 12);
            this.heading.Size = new Size(541, 44);
            this.heading.Font = new Font("Segoe UI Semibold", 11F);

            this.peopleList.Name = "peopleList";
            this.peopleList.Location = new Point(14, 58);
            this.peopleList.Size = new Size(541, 237);
            this.peopleList.CheckOnClick = true;
            this.peopleList.ItemCheck += this.PersonChecked;

            this.noteLabel.Name = "noteLabel";
            this.noteLabel.Text = "Assignment note";
            this.noteLabel.Location = new Point(14, 306);
            this.noteLabel.Size = new Size(150, 25);

            this.noteInput.Name = "noteInput";
            this.noteInput.Location = new Point(14, 333);
            this.noteInput.Size = new Size(541, 64);
            this.noteInput.Multiline = true;
            this.noteInput.MaxLength = 2000;

            this.notifyInput.Name = "notifyInput";
            this.notifyInput.Text = "Send in-app notifications";
            this.notifyInput.Location = new Point(14, 406);
            this.notifyInput.Size = new Size(260, 25);
            this.notifyInput.Checked = true;

            this.statusLabel.Name = "statusLabel";
            this.statusLabel.Location = new Point(14, 441);
            this.statusLabel.Size = new Size(541, 48);

            this.saveButton.Name = "saveButton";
            this.saveButton.Text = "Save assignment";
            this.saveButton.Location = new Point(335, 495);
            this.saveButton.Size = new Size(122, 29);
            this.saveButton.Enabled = false;
            this.saveButton.Click += this.SaveClicked;

            this.cancelButton.Name = "cancelButton";
            this.cancelButton.Text = "Cancel";
            this.cancelButton.Location = new Point(468, 495);
            this.cancelButton.Size = new Size(87, 29);
            this.cancelButton.DialogResult = DialogResult.Cancel;

            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.ClientSize = new Size(570, 537);
            this.Controls.AddRange(new Control[] {
                this.heading, this.peopleList, this.noteLabel, this.noteInput, this.notifyInput,
                this.statusLabel, this.saveButton, this.cancelButton });
            this.Font = new Font("Segoe UI", 10F);
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.MaximizeBox = false;
            this.MinimizeBox = false;
            this.Name = "PmsTaskAssignmentForm";
            this.StartPosition = FormStartPosition.CenterParent;
            this.Text = "Assign task";
            this.CancelButton = this.cancelButton;
            this.Load += this.AssignmentLoaded;
            this.ResumeLayout(false);
            this.PerformLayout();
        }

        private Label heading;
        private CheckedListBox peopleList;
        private Label noteLabel;
        private RadTextBox noteInput;
        private CheckBox notifyInput;
        private Label statusLabel;
        private RadButton saveButton;
        private RadButton cancelButton;
    }
}
