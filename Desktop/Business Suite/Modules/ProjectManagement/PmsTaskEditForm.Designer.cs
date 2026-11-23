#nullable disable
using System.Drawing;
using System.Windows.Forms;
using Telerik.WinControls.UI;

namespace Business_Suite
{
    partial class PmsTaskEditForm
    {
        private void InitializeComponent()
        {
            this.keyLabel = new Label();
            this.keyInput = new RadTextBox();
            this.titleLabel = new Label();
            this.titleInput = new RadTextBox();
            this.descriptionLabel = new Label();
            this.descriptionInput = new RadTextBox();
            this.statusLabel = new Label();
            this.statusInput = new RadDropDownList();
            this.priorityLabel = new Label();
            this.priorityInput = new RadDropDownList();
            this.startLabel = new Label();
            this.startInput = new RadDateTimePicker();
            this.dueLabel = new Label();
            this.dueInput = new RadDateTimePicker();
            this.hoursLabel = new Label();
            this.hoursInput = new RadTextBox();
            this.saveButton = new RadButton();
            this.cancelButton = new RadButton();
            this.errorLabel = new Label();
            this.SuspendLayout();

            this.keyLabel.Name = "keyLabel";
            this.keyLabel.Text = "Task key";
            this.keyLabel.Location = new Point(15, 23);
            this.keyLabel.Size = new Size(142, 24);
            this.keyInput.Name = "keyInput";
            this.keyInput.Location = new Point(160, 20);
            this.keyInput.Size = new Size(386, 25);
            this.keyInput.TabIndex = 0;

            this.titleLabel.Name = "titleLabel";
            this.titleLabel.Text = "Task title";
            this.titleLabel.Location = new Point(15, 59);
            this.titleLabel.Size = new Size(142, 24);
            this.titleInput.Name = "titleInput";
            this.titleInput.Location = new Point(160, 56);
            this.titleInput.Size = new Size(386, 25);
            this.titleInput.TabIndex = 1;

            this.descriptionLabel.Name = "descriptionLabel";
            this.descriptionLabel.Text = "Description";
            this.descriptionLabel.Location = new Point(15, 95);
            this.descriptionLabel.Size = new Size(142, 24);
            this.descriptionInput.Name = "descriptionInput";
            this.descriptionInput.Location = new Point(160, 92);
            this.descriptionInput.Size = new Size(386, 74);
            this.descriptionInput.TabIndex = 2;

            this.statusLabel.Name = "statusLabel";
            this.statusLabel.Text = "Status";
            this.statusLabel.Location = new Point(15, 180);
            this.statusLabel.Size = new Size(142, 24);
            this.statusInput.Name = "statusInput";
            this.statusInput.Location = new Point(160, 177);
            this.statusInput.Size = new Size(386, 25);
            this.statusInput.TabIndex = 3;

            this.priorityLabel.Name = "priorityLabel";
            this.priorityLabel.Text = "Priority";
            this.priorityLabel.Location = new Point(15, 216);
            this.priorityLabel.Size = new Size(142, 24);
            this.priorityInput.Name = "priorityInput";
            this.priorityInput.Location = new Point(160, 213);
            this.priorityInput.Size = new Size(386, 25);
            this.priorityInput.TabIndex = 4;

            this.startLabel.Name = "startLabel";
            this.startLabel.Text = "Start date";
            this.startLabel.Location = new Point(15, 252);
            this.startLabel.Size = new Size(142, 24);
            this.startInput.Name = "startInput";
            this.startInput.Location = new Point(160, 249);
            this.startInput.Size = new Size(386, 25);
            this.startInput.TabIndex = 5;

            this.dueLabel.Name = "dueLabel";
            this.dueLabel.Text = "Due date";
            this.dueLabel.Location = new Point(15, 288);
            this.dueLabel.Size = new Size(142, 24);
            this.dueInput.Name = "dueInput";
            this.dueInput.Location = new Point(160, 285);
            this.dueInput.Size = new Size(386, 25);
            this.dueInput.TabIndex = 6;

            this.hoursLabel.Name = "hoursLabel";
            this.hoursLabel.Text = "Estimated hours";
            this.hoursLabel.Location = new Point(15, 324);
            this.hoursLabel.Size = new Size(142, 24);
            this.hoursInput.Name = "hoursInput";
            this.hoursInput.Location = new Point(160, 321);
            this.hoursInput.Size = new Size(386, 25);
            this.hoursInput.TabIndex = 7;

            this.statusInput.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
            this.statusInput.Items.AddRange(new RadListDataItem[] {
                new RadListDataItem("Backlog"), new RadListDataItem("To Do"), new RadListDataItem("In Progress"),
                new RadListDataItem("In Review"), new RadListDataItem("Blocked"), new RadListDataItem("Done"),
                new RadListDataItem("Completed"), new RadListDataItem("Closed"), new RadListDataItem("Resolved"),
                new RadListDataItem("Cancelled"), new RadListDataItem("Canceled"), new RadListDataItem("Rejected") });
            this.priorityInput.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
            this.priorityInput.Items.AddRange(new RadListDataItem[] {
                new RadListDataItem("Low"), new RadListDataItem("Medium"), new RadListDataItem("High"),
                new RadListDataItem("Urgent"), new RadListDataItem("Critical") });
            this.keyInput.ReadOnly = true;
            this.keyInput.TabStop = false;
            this.titleInput.MaxLength = 220;
            this.descriptionInput.Multiline = true;
            this.descriptionInput.ScrollBars = ScrollBars.Vertical;
            this.startInput.Format = DateTimePickerFormat.Short;
            this.startInput.ShowCheckBox = true;
            this.startInput.Checked = false;
            this.dueInput.Format = DateTimePickerFormat.Short;
            this.dueInput.ShowCheckBox = true;
            this.dueInput.Checked = false;

            this.errorLabel.Name = "errorLabel";
            this.errorLabel.Location = new Point(15, 355);
            this.errorLabel.Size = new Size(530, 45);
            this.errorLabel.ForeColor = Color.Firebrick;

            this.saveButton.Name = "saveButton";
            this.saveButton.Text = "Save";
            this.saveButton.Location = new Point(363, 410);
            this.saveButton.Size = new Size(84, 30);
            this.saveButton.Click += this.SaveClicked;
            this.saveButton.TabIndex = 8;

            this.cancelButton.Name = "cancelButton";
            this.cancelButton.Text = "Cancel";
            this.cancelButton.Location = new Point(462, 410);
            this.cancelButton.Size = new Size(84, 30);
            this.cancelButton.DialogResult = DialogResult.Cancel;
            this.cancelButton.TabIndex = 9;

            this.AcceptButton = this.saveButton;
            this.CancelButton = this.cancelButton;
            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.ClientSize = new Size(562, 455);
            this.Controls.AddRange(new Control[] {
                this.keyLabel, this.keyInput,
                this.titleLabel, this.titleInput,
                this.descriptionLabel, this.descriptionInput,
                this.statusLabel, this.statusInput,
                this.priorityLabel, this.priorityInput,
                this.startLabel, this.startInput,
                this.dueLabel, this.dueInput,
                this.hoursLabel, this.hoursInput,
                this.errorLabel, this.saveButton, this.cancelButton
            });
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.MaximizeBox = false;
            this.MinimizeBox = false;
            this.ShowInTaskbar = false;
            this.Font = new Font("Segoe UI", 10F);
            this.Name = "PmsTaskEditForm";
            this.StartPosition = FormStartPosition.CenterParent;
            this.Text = "Edit task";
            this.ResumeLayout(false);
            this.PerformLayout();
        }

        private Label keyLabel;
        private RadTextBox keyInput;
        private Label titleLabel;
        private RadTextBox titleInput;
        private Label descriptionLabel;
        private RadTextBox descriptionInput;
        private Label statusLabel;
        private RadDropDownList statusInput;
        private Label priorityLabel;
        private RadDropDownList priorityInput;
        private Label startLabel;
        private RadDateTimePicker startInput;
        private Label dueLabel;
        private RadDateTimePicker dueInput;
        private Label hoursLabel;
        private RadTextBox hoursInput;
        private RadButton saveButton;
        private RadButton cancelButton;
        private Label errorLabel;
    }
}
