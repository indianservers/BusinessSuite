#nullable disable
using System.Drawing;
using System.Windows.Forms;
using Telerik.WinControls.UI;

namespace Business_Suite
{
    partial class PmsProjectEditForm
    {
        private void InitializeComponent()
        {
            this.workspaceLabel = new Label();
            this.workspaceInput = new RadDropDownList();
            this.keyLabel = new Label();
            this.keyInput = new RadTextBox();
            this.nameLabel = new Label();
            this.nameInput = new RadTextBox();
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
            this.budgetLabel = new Label();
            this.budgetInput = new RadTextBox();
            this.saveButton = new RadButton();
            this.cancelButton = new RadButton();
            this.errorLabel = new Label();
            this.SuspendLayout();

            this.workspaceLabel.Name = "workspaceLabel";
            this.workspaceLabel.Text = "Workspace";
            this.workspaceLabel.Location = new Point(15, 23);
            this.workspaceLabel.Size = new Size(142, 24);

            this.workspaceInput.Name = "workspaceInput";
            this.workspaceInput.Location = new Point(160, 20);
            this.workspaceInput.Size = new Size(386, 25);
            this.workspaceInput.TabIndex = 0;

            this.keyLabel.Name = "keyLabel";
            this.keyLabel.Text = "Project key";
            this.keyLabel.Location = new Point(15, 59);
            this.keyLabel.Size = new Size(142, 24);

            this.keyInput.Name = "keyInput";
            this.keyInput.Location = new Point(160, 56);
            this.keyInput.Size = new Size(386, 25);
            this.keyInput.TabIndex = 1;

            this.nameLabel.Name = "nameLabel";
            this.nameLabel.Text = "Project name";
            this.nameLabel.Location = new Point(15, 95);
            this.nameLabel.Size = new Size(142, 24);

            this.nameInput.Name = "nameInput";
            this.nameInput.Location = new Point(160, 92);
            this.nameInput.Size = new Size(386, 25);
            this.nameInput.TabIndex = 2;

            this.descriptionLabel.Name = "descriptionLabel";
            this.descriptionLabel.Text = "Description";
            this.descriptionLabel.Location = new Point(15, 131);
            this.descriptionLabel.Size = new Size(142, 24);

            this.descriptionInput.Name = "descriptionInput";
            this.descriptionInput.Location = new Point(160, 128);
            this.descriptionInput.Size = new Size(386, 74);
            this.descriptionInput.TabIndex = 3;

            this.statusLabel.Name = "statusLabel";
            this.statusLabel.Text = "Status";
            this.statusLabel.Location = new Point(15, 216);
            this.statusLabel.Size = new Size(142, 24);

            this.statusInput.Name = "statusInput";
            this.statusInput.Location = new Point(160, 213);
            this.statusInput.Size = new Size(386, 25);
            this.statusInput.TabIndex = 4;

            this.priorityLabel.Name = "priorityLabel";
            this.priorityLabel.Text = "Priority";
            this.priorityLabel.Location = new Point(15, 252);
            this.priorityLabel.Size = new Size(142, 24);

            this.priorityInput.Name = "priorityInput";
            this.priorityInput.Location = new Point(160, 249);
            this.priorityInput.Size = new Size(386, 25);
            this.priorityInput.TabIndex = 5;

            this.startLabel.Name = "startLabel";
            this.startLabel.Text = "Start date";
            this.startLabel.Location = new Point(15, 288);
            this.startLabel.Size = new Size(142, 24);

            this.startInput.Name = "startInput";
            this.startInput.Location = new Point(160, 285);
            this.startInput.Size = new Size(386, 25);
            this.startInput.TabIndex = 6;

            this.dueLabel.Name = "dueLabel";
            this.dueLabel.Text = "Due date";
            this.dueLabel.Location = new Point(15, 324);
            this.dueLabel.Size = new Size(142, 24);

            this.dueInput.Name = "dueInput";
            this.dueInput.Location = new Point(160, 321);
            this.dueInput.Size = new Size(386, 25);
            this.dueInput.TabIndex = 7;

            this.budgetLabel.Name = "budgetLabel";
            this.budgetLabel.Text = "Budget amount";
            this.budgetLabel.Location = new Point(15, 360);
            this.budgetLabel.Size = new Size(142, 24);

            this.budgetInput.Name = "budgetInput";
            this.budgetInput.Location = new Point(160, 357);
            this.budgetInput.Size = new Size(386, 25);
            this.budgetInput.TabIndex = 8;

            this.workspaceInput.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
            this.statusInput.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
            this.statusInput.Items.AddRange(new RadListDataItem[] {
                new RadListDataItem("Draft"), new RadListDataItem("Planned"), new RadListDataItem("Active"),
                new RadListDataItem("On Hold"), new RadListDataItem("Completed"), new RadListDataItem("Cancelled"),
                new RadListDataItem("Archived") });
            this.priorityInput.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
            this.priorityInput.Items.AddRange(new RadListDataItem[] {
                new RadListDataItem("Low"), new RadListDataItem("Medium"), new RadListDataItem("High"),
                new RadListDataItem("Critical") });
            this.keyInput.CharacterCasing = CharacterCasing.Upper;
            this.keyInput.MaxLength = 10;
            this.nameInput.MaxLength = 180;
            this.descriptionInput.Multiline = true;
            this.startInput.Format = DateTimePickerFormat.Short;
            this.startInput.ShowCheckBox = true;
            this.startInput.Checked = false;
            this.dueInput.Format = DateTimePickerFormat.Short;
            this.dueInput.ShowCheckBox = true;
            this.dueInput.Checked = false;

            this.errorLabel.Name = "errorLabel";
            this.errorLabel.Location = new Point(15, 390);
            this.errorLabel.Size = new Size(530, 42);
            this.errorLabel.ForeColor = Color.Firebrick;

            this.saveButton.Name = "saveButton";
            this.saveButton.Text = "Save";
            this.saveButton.Location = new Point(363, 435);
            this.saveButton.Size = new Size(84, 30);
            this.saveButton.Click += this.saveButton_Click;
            this.saveButton.TabIndex = 9;

            this.cancelButton.Name = "cancelButton";
            this.cancelButton.Text = "Cancel";
            this.cancelButton.Location = new Point(462, 435);
            this.cancelButton.Size = new Size(84, 30);
            this.cancelButton.DialogResult = DialogResult.Cancel;
            this.cancelButton.TabIndex = 10;

            this.AcceptButton = this.saveButton;
            this.CancelButton = this.cancelButton;
            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.ClientSize = new Size(562, 480);
            this.Controls.AddRange(new Control[] {
                this.workspaceLabel, this.workspaceInput,
                this.keyLabel, this.keyInput,
                this.nameLabel, this.nameInput,
                this.descriptionLabel, this.descriptionInput,
                this.statusLabel, this.statusInput,
                this.priorityLabel, this.priorityInput,
                this.startLabel, this.startInput,
                this.dueLabel, this.dueInput,
                this.budgetLabel, this.budgetInput,
                this.errorLabel, this.saveButton, this.cancelButton
            });
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.MaximizeBox = false;
            this.MinimizeBox = false;
            this.ShowInTaskbar = false;
            this.Font = new Font("Segoe UI", 10F);
            this.Name = "PmsProjectEditForm";
            this.StartPosition = FormStartPosition.CenterParent;
            this.Text = "Project";
            this.ResumeLayout(false);
            this.PerformLayout();
        }

        private Label workspaceLabel;
        private RadDropDownList workspaceInput;
        private Label keyLabel;
        private RadTextBox keyInput;
        private Label nameLabel;
        private RadTextBox nameInput;
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
        private Label budgetLabel;
        private RadTextBox budgetInput;
        private RadButton saveButton;
        private RadButton cancelButton;
        private Label errorLabel;
    }
}
