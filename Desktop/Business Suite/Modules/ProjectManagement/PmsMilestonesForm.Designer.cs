#nullable disable
using System.Drawing;
using System.Windows.Forms;
using Telerik.WinControls.UI;

namespace Business_Suite
{
    partial class PmsMilestonesForm
    {
        private void InitializeComponent()
        {
            this.heading = new Label();
            this.grid = new RadGridView();
            this.editor = new Panel();
            this.nameColumn = new GridViewTextBoxColumn();
            this.statusColumn = new GridViewTextBoxColumn();
            this.startColumn = new GridViewTextBoxColumn();
            this.dueColumn = new GridViewTextBoxColumn();
            this.progressColumn = new GridViewTextBoxColumn();
            this.approvalColumn = new GridViewTextBoxColumn();
            this.nameLabel = new Label();
            this.nameInput = new RadTextBox();
            this.descriptionLabel = new Label();
            this.descriptionInput = new RadTextBox();
            this.statusLabel = new Label();
            this.statusInput = new RadDropDownList();
            this.startLabel = new Label();
            this.startInput = new RadDateTimePicker();
            this.dueLabel = new Label();
            this.dueInput = new RadDateTimePicker();
            this.progressLabel = new Label();
            this.progressInput = new RadSpinEditor();
            this.ownerLabel = new Label();
            this.ownerInput = new RadDropDownList();
            this.newButton = new RadButton();
            this.editButton = new RadButton();
            this.submitButton = new RadButton();
            this.approveButton = new RadButton();
            this.rejectButton = new RadButton();
            this.reasonInput = new RadTextBox();
            this.saveButton = new RadButton();
            this.cancelEditButton = new RadButton();
            this.closeButton = new RadButton();
            this.statusText = new Label();
            ((System.ComponentModel.ISupportInitialize)this.grid).BeginInit();
            ((System.ComponentModel.ISupportInitialize)this.grid.MasterTemplate).BeginInit();
            this.editor.SuspendLayout();
            this.SuspendLayout();

            this.heading.Name = "heading";
            this.heading.Location = new Point(14, 13);
            this.heading.Size = new Size(600, 29);
            this.heading.Font = new Font("Segoe UI Semibold", 11F);

            this.nameColumn.Name = "nameColumn";
            this.nameColumn.FieldName = "name";
            this.nameColumn.HeaderText = "Milestone";
            this.nameColumn.Width = 220;

            this.statusColumn.Name = "statusColumn";
            this.statusColumn.FieldName = "status";
            this.statusColumn.HeaderText = "Status";
            this.statusColumn.Width = 110;

            this.startColumn.Name = "startColumn";
            this.startColumn.FieldName = "start_date";
            this.startColumn.HeaderText = "Start";
            this.startColumn.Width = 112;
            this.startColumn.FormatString = "{0:d}";

            this.dueColumn.Name = "dueColumn";
            this.dueColumn.FieldName = "due_date";
            this.dueColumn.HeaderText = "Due";
            this.dueColumn.Width = 112;
            this.dueColumn.FormatString = "{0:d}";

            this.progressColumn.Name = "progressColumn";
            this.progressColumn.FieldName = "progress";
            this.progressColumn.HeaderText = "Progress (%)";
            this.progressColumn.Width = 100;

            this.approvalColumn.Name = "approvalColumn";
            this.approvalColumn.FieldName = "client_approval_status";
            this.approvalColumn.HeaderText = "Client approval";
            this.approvalColumn.Width = 130;
            this.grid.Name = "grid";
            this.grid.Location = new Point(14, 92);
            this.grid.Size = new Size(649, 429);
            this.grid.AutoGenerateColumns = false;
            this.grid.ReadOnly = true;
            this.grid.MasterTemplate.AllowAddNewRow = false;
            this.grid.MasterTemplate.AllowDeleteRow = false;
            this.grid.MasterTemplate.AllowEditRow = false;
            this.grid.MasterTemplate.EnableFiltering = true;
            this.grid.MasterTemplate.ShowFilteringRow = true;
            this.grid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] {
                this.nameColumn, this.statusColumn, this.startColumn, this.dueColumn, this.progressColumn, this.approvalColumn });
            this.grid.CurrentRowChanged += this.SelectionChanged;

            this.nameLabel.Name = "nameLabel";
            this.nameLabel.Text = "Milestone name";
            this.nameLabel.Location = new Point(12, 9);
            this.nameLabel.Size = new Size(272, 23);
            this.nameInput.Name = "nameInput";
            this.nameInput.Location = new Point(12, 31);
            this.nameInput.Size = new Size(300, 25);

            this.descriptionLabel.Name = "descriptionLabel";
            this.descriptionLabel.Text = "Description";
            this.descriptionLabel.Location = new Point(12, 63);
            this.descriptionLabel.Size = new Size(272, 23);
            this.descriptionInput.Name = "descriptionInput";
            this.descriptionInput.Location = new Point(12, 85);
            this.descriptionInput.Size = new Size(300, 62);

            this.statusLabel.Name = "statusLabel";
            this.statusLabel.Text = "Status";
            this.statusLabel.Location = new Point(12, 153);
            this.statusLabel.Size = new Size(272, 23);
            this.statusInput.Name = "statusInput";
            this.statusInput.Location = new Point(12, 175);
            this.statusInput.Size = new Size(300, 25);

            this.startLabel.Name = "startLabel";
            this.startLabel.Text = "Start date";
            this.startLabel.Location = new Point(12, 207);
            this.startLabel.Size = new Size(272, 23);
            this.startInput.Name = "startInput";
            this.startInput.Location = new Point(12, 229);
            this.startInput.Size = new Size(300, 25);

            this.dueLabel.Name = "dueLabel";
            this.dueLabel.Text = "Due date";
            this.dueLabel.Location = new Point(12, 261);
            this.dueLabel.Size = new Size(272, 23);
            this.dueInput.Name = "dueInput";
            this.dueInput.Location = new Point(12, 283);
            this.dueInput.Size = new Size(300, 25);

            this.progressLabel.Name = "progressLabel";
            this.progressLabel.Text = "Progress (%)";
            this.progressLabel.Location = new Point(12, 315);
            this.progressLabel.Size = new Size(272, 23);
            this.progressInput.Name = "progressInput";
            this.progressInput.Location = new Point(12, 337);
            this.progressInput.Size = new Size(300, 25);
            this.nameInput.MaxLength = 180;
            this.descriptionInput.MaxLength = 8000;
            this.descriptionInput.Multiline = true;
            this.descriptionInput.ScrollBars = ScrollBars.Vertical;
            this.statusInput.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
            this.statusInput.Items.AddRange(new RadListDataItem[] {
                new RadListDataItem("Not Started"), new RadListDataItem("In Progress"), new RadListDataItem("On Hold"),
                new RadListDataItem("Completed"), new RadListDataItem("Cancelled") });
            this.statusInput.SelectedIndex = 0;
            this.statusInput.SelectedIndexChanged += this.MilestoneStatusChanged;
            this.startInput.Format = DateTimePickerFormat.Short;
            this.startInput.ShowCheckBox = true;
            this.dueInput.Format = DateTimePickerFormat.Short;
            this.dueInput.ShowCheckBox = true;
            this.progressInput.Minimum = 0;
            this.progressInput.Maximum = 100;

            this.ownerLabel.Name = "ownerLabel";
            this.ownerLabel.Text = "Owner";
            this.ownerLabel.Location = new Point(12, 365);
            this.ownerLabel.Size = new Size(180, 22);
            this.ownerInput.Name = "ownerInput";
            this.ownerInput.Location = new Point(12, 387);
            this.ownerInput.Size = new Size(300, 25);
            this.ownerInput.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;

            this.editor.Name = "editor";
            this.editor.Location = new Point(674, 89);
            this.editor.Size = new Size(325, 466);
            this.editor.Controls.AddRange(new Control[] {
                this.nameLabel, this.nameInput,
                this.descriptionLabel, this.descriptionInput,
                this.statusLabel, this.statusInput,
                this.startLabel, this.startInput,
                this.dueLabel, this.dueInput,
                this.progressLabel, this.progressInput, this.ownerLabel, this.ownerInput,
                this.saveButton, this.cancelEditButton });

            this.newButton.Name = "newButton";
            this.newButton.Text = "New milestone";
            this.newButton.Location = new Point(14, 48);
            this.newButton.Size = new Size(106, 29);
            this.newButton.Click += this.NewClicked;

            this.editButton.Name = "editButton";
            this.editButton.Text = "Edit milestone";
            this.editButton.Location = new Point(128, 48);
            this.editButton.Size = new Size(106, 29);
            this.editButton.Click += this.EditClicked;

            this.submitButton.Name = "submitButton";
            this.submitButton.Text = "Submit for client approval";
            this.submitButton.Location = new Point(242, 48);
            this.submitButton.Size = new Size(178, 29);
            this.submitButton.Click += this.SubmitClicked;

            this.approveButton.Name = "approveButton";
            this.approveButton.Text = "Approve";
            this.approveButton.Location = new Point(432, 48);
            this.approveButton.Size = new Size(83, 29);
            this.approveButton.Click += this.ApproveClicked;

            this.rejectButton.Name = "rejectButton";
            this.rejectButton.Text = "Reject";
            this.rejectButton.Location = new Point(524, 48);
            this.rejectButton.Size = new Size(80, 29);
            this.rejectButton.Click += this.RejectClicked;

            this.reasonInput.Name = "reasonInput";
            this.reasonInput.NullText = "Reason for rejection";
            this.reasonInput.Location = new Point(614, 50);
            this.reasonInput.Size = new Size(386, 25);
            this.reasonInput.MaxLength = 8000;
            this.reasonInput.TextChanged += this.ReasonChanged;

            this.saveButton.Name = "saveButton";
            this.saveButton.Text = "Save";
            this.saveButton.Location = new Point(128, 424);
            this.saveButton.Size = new Size(82, 29);
            this.saveButton.Click += this.SaveClicked;

            this.cancelEditButton.Name = "cancelEditButton";
            this.cancelEditButton.Text = "Cancel";
            this.cancelEditButton.Location = new Point(225, 424);
            this.cancelEditButton.Size = new Size(87, 29);
            this.cancelEditButton.Click += this.CancelEditClicked;

            this.closeButton.Name = "closeButton";
            this.closeButton.Text = "Close";
            this.closeButton.Location = new Point(904, 565);
            this.closeButton.Size = new Size(95, 29);
            this.closeButton.Click += this.CloseClicked;
            this.closeButton.DialogResult = DialogResult.Cancel;
            this.statusText.Name = "statusText";
            this.statusText.Location = new Point(14, 565);
            this.statusText.Size = new Size(871, 38);

            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.ClientSize = new Size(1013, 612);
            this.Controls.AddRange(new Control[] {
                this.heading, this.grid, this.editor, this.newButton, this.editButton, this.submitButton,
                this.approveButton, this.rejectButton, this.reasonInput, this.closeButton, this.statusText });
            this.Font = new Font("Segoe UI", 10F);
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.MaximizeBox = false;
            this.MinimizeBox = false;
            this.Name = "PmsMilestonesForm";
            this.StartPosition = FormStartPosition.CenterParent;
            this.Text = "Project milestones";
            this.CancelButton = this.closeButton;
            this.Load += this.MilestonesLoaded;
            ((System.ComponentModel.ISupportInitialize)this.grid.MasterTemplate).EndInit();
            ((System.ComponentModel.ISupportInitialize)this.grid).EndInit();
            this.editor.ResumeLayout(false);
            this.editor.PerformLayout();
            this.ResumeLayout(false);
            this.PerformLayout();
        }

        private Label heading;
        private RadGridView grid;
        private GridViewTextBoxColumn nameColumn;
        private GridViewTextBoxColumn statusColumn;
        private GridViewTextBoxColumn startColumn;
        private GridViewTextBoxColumn dueColumn;
        private GridViewTextBoxColumn progressColumn;
        private GridViewTextBoxColumn approvalColumn;
        private Panel editor;
        private Label nameLabel;
        private RadTextBox nameInput;
        private Label descriptionLabel;
        private RadTextBox descriptionInput;
        private Label statusLabel;
        private RadDropDownList statusInput;
        private Label startLabel;
        private RadDateTimePicker startInput;
        private Label dueLabel;
        private RadDateTimePicker dueInput;
        private Label progressLabel;
        private RadSpinEditor progressInput;
        private Label ownerLabel;
        private RadDropDownList ownerInput;
        private RadButton newButton;
        private RadButton editButton;
        private RadButton submitButton;
        private RadButton approveButton;
        private RadButton rejectButton;
        private RadTextBox reasonInput;
        private RadButton saveButton;
        private RadButton cancelEditButton;
        private RadButton closeButton;
        private Label statusText;
    }
}
