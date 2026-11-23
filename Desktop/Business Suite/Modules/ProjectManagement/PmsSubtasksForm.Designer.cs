#nullable disable
using System.Drawing;
using System.Windows.Forms;
using Telerik.WinControls.UI;

namespace Business_Suite
{
    partial class PmsSubtasksForm
    {
        private void InitializeComponent()
        {
            this.heading = new Label();
            this.grid = new RadGridView();
            this.keyColumn = new GridViewTextBoxColumn();
            this.titleColumn = new GridViewTextBoxColumn();
            this.statusColumn = new GridViewTextBoxColumn();
            this.priorityColumn = new GridViewTextBoxColumn();
            this.dueColumn = new GridViewTextBoxColumn();
            this.titleInput = new RadTextBox();
            this.priorityInput = new RadDropDownList();
            this.dueInput = new RadDateTimePicker();
            this.inheritInput = new CheckBox();
            this.addButton = new RadButton();
            this.editButton = new RadButton();
            this.assignButton = new RadButton();
            this.trashButton = new RadButton();
            this.upButton = new RadButton();
            this.downButton = new RadButton();
            this.refreshButton = new RadButton();
            this.closeButton = new RadButton();
            this.statusLabel = new Label();
            ((System.ComponentModel.ISupportInitialize)this.grid).BeginInit();
            ((System.ComponentModel.ISupportInitialize)this.grid.MasterTemplate).BeginInit();
            this.SuspendLayout();

            this.heading.Name = "heading";
            this.heading.Location = new Point(14, 13);
            this.heading.Size = new Size(688, 29);
            this.heading.Font = new Font("Segoe UI Semibold", 11F);

            this.keyColumn.Name = "keyColumn";
            this.keyColumn.FieldName = "task_key";
            this.keyColumn.HeaderText = "Task key";
            this.keyColumn.AllowSort = false;
            this.keyColumn.Width = 149;

            this.titleColumn.Name = "titleColumn";
            this.titleColumn.FieldName = "title";
            this.titleColumn.HeaderText = "Subtask";
            this.titleColumn.AllowSort = false;
            this.titleColumn.Width = 229;

            this.statusColumn.Name = "statusColumn";
            this.statusColumn.FieldName = "status";
            this.statusColumn.HeaderText = "Status";
            this.statusColumn.AllowSort = false;
            this.statusColumn.Width = 108;

            this.priorityColumn.Name = "priorityColumn";
            this.priorityColumn.FieldName = "priority";
            this.priorityColumn.HeaderText = "Priority";
            this.priorityColumn.AllowSort = false;
            this.priorityColumn.Width = 108;

            this.dueColumn.Name = "dueColumn";
            this.dueColumn.FieldName = "due_date";
            this.dueColumn.HeaderText = "Due";
            this.dueColumn.AllowSort = false;
            this.dueColumn.Width = 102;
            this.dueColumn.FormatString = "{0:d}";
            this.grid.Name = "grid";
            this.grid.Location = new Point(14, 48);
            this.grid.Size = new Size(692, 295);
            this.grid.AutoGenerateColumns = false;
            this.grid.ReadOnly = true;
            this.grid.MasterTemplate.AllowAddNewRow = false;
            this.grid.MasterTemplate.AllowDeleteRow = false;
            this.grid.MasterTemplate.AllowEditRow = false;
            this.grid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] {
                this.keyColumn, this.titleColumn, this.statusColumn, this.priorityColumn, this.dueColumn });
            this.grid.CurrentRowChanged += this.SelectionChanged;

            this.titleInput.Name = "titleInput";
            this.titleInput.NullText = "New subtask title";
            this.titleInput.Location = new Point(14, 356);
            this.titleInput.Size = new Size(689, 26);
            this.titleInput.MaxLength = 220;
            this.titleInput.TextChanged += this.TitleChanged;

            this.priorityInput.Name = "priorityInput";
            this.priorityInput.Location = new Point(14, 397);
            this.priorityInput.Size = new Size(119, 25);
            this.priorityInput.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
            this.priorityInput.Items.AddRange(new RadListDataItem[] {
                new RadListDataItem("Low"), new RadListDataItem("Medium"), new RadListDataItem("High"),
                new RadListDataItem("Urgent"), new RadListDataItem("Critical") });
            this.priorityInput.SelectedIndex = 1;

            this.dueInput.Name = "dueInput";
            this.dueInput.Location = new Point(146, 397);
            this.dueInput.Size = new Size(154, 25);
            this.dueInput.Format = DateTimePickerFormat.Short;
            this.dueInput.ShowCheckBox = true;
            this.dueInput.Checked = false;

            this.inheritInput.Name = "inheritInput";
            this.inheritInput.Text = "Inherit parent assignees";
            this.inheritInput.Location = new Point(316, 396);
            this.inheritInput.Size = new Size(263, 28);

            this.addButton.Name = "addButton";
            this.addButton.Text = "Add subtask";
            this.addButton.Location = new Point(594, 395);
            this.addButton.Size = new Size(112, 29);
            this.addButton.Click += this.AddClicked;

            this.editButton.Name = "editButton";
            this.editButton.Text = "Edit";
            this.editButton.Location = new Point(14, 443);
            this.editButton.Size = new Size(81, 29);
            this.editButton.Click += this.EditClicked;

            this.assignButton.Name = "assignButton";
            this.assignButton.Text = "Assign";
            this.assignButton.Location = new Point(103, 443);
            this.assignButton.Size = new Size(81, 29);
            this.assignButton.Click += this.AssignClicked;

            this.trashButton.Name = "trashButton";
            this.trashButton.Text = "Move to Trash";
            this.trashButton.Location = new Point(192, 443);
            this.trashButton.Size = new Size(105, 29);
            this.trashButton.Click += this.TrashClicked;

            this.upButton.Name = "upButton";
            this.upButton.Text = "Move up";
            this.upButton.Location = new Point(307, 443);
            this.upButton.Size = new Size(90, 29);
            this.upButton.Click += this.UpClicked;

            this.downButton.Name = "downButton";
            this.downButton.Text = "Move down";
            this.downButton.Location = new Point(406, 443);
            this.downButton.Size = new Size(95, 29);
            this.downButton.Click += this.DownClicked;

            this.refreshButton.Name = "refreshButton";
            this.refreshButton.Text = "Refresh";
            this.refreshButton.Location = new Point(510, 443);
            this.refreshButton.Size = new Size(88, 29);
            this.refreshButton.Click += this.RefreshClicked;

            this.statusLabel.Name = "statusLabel";
            this.statusLabel.Location = new Point(14, 486);
            this.statusLabel.Size = new Size(568, 41);

            this.closeButton.Name = "closeButton";
            this.closeButton.Text = "Close";
            this.closeButton.Location = new Point(618, 490);
            this.closeButton.Size = new Size(88, 29);
            this.closeButton.DialogResult = DialogResult.Cancel;

            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.ClientSize = new Size(723, 537);
            this.Controls.AddRange(new Control[] {
                this.heading, this.grid, this.titleInput, this.priorityInput, this.dueInput, this.inheritInput,
                this.addButton, this.editButton, this.assignButton, this.trashButton, this.upButton, this.downButton, this.refreshButton, this.closeButton, this.statusLabel });
            this.Font = new Font("Segoe UI", 10F);
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.MaximizeBox = false;
            this.MinimizeBox = false;
            this.Name = "PmsSubtasksForm";
            this.StartPosition = FormStartPosition.CenterParent;
            this.Text = "Subtasks";
            this.CancelButton = this.closeButton;
            this.Load += this.SubtasksLoaded;
            ((System.ComponentModel.ISupportInitialize)this.grid.MasterTemplate).EndInit();
            ((System.ComponentModel.ISupportInitialize)this.grid).EndInit();
            this.ResumeLayout(false);
            this.PerformLayout();
        }

        private Label heading;
        private RadGridView grid;
        private GridViewTextBoxColumn keyColumn;
        private GridViewTextBoxColumn titleColumn;
        private GridViewTextBoxColumn statusColumn;
        private GridViewTextBoxColumn priorityColumn;
        private GridViewTextBoxColumn dueColumn;
        private RadTextBox titleInput;
        private RadDropDownList priorityInput;
        private RadDateTimePicker dueInput;
        private CheckBox inheritInput;
        private RadButton addButton;
        private RadButton editButton;
        private RadButton assignButton;
        private RadButton trashButton;
        private RadButton upButton;
        private RadButton downButton;
        private RadButton refreshButton;
        private Label statusLabel;
        private RadButton closeButton;
    }
}
