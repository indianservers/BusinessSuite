#nullable disable
using System.Drawing;
using System.Windows.Forms;
using Telerik.WinControls.UI;

namespace Business_Suite
{
    partial class PmsRisksForm
    {
        private void InitializeComponent()
        {
            this.heading = new Label();
            this.grid = new RadGridView();
            this.titleColumn = new GridViewTextBoxColumn();
            this.categoryColumn = new GridViewTextBoxColumn();
            this.statusColumn = new GridViewTextBoxColumn();
            this.severityColumn = new GridViewTextBoxColumn();
            this.scoreColumn = new GridViewTextBoxColumn();
            this.ownerColumn = new GridViewTextBoxColumn();
            this.taskColumn = new GridViewTextBoxColumn();
            this.dueColumn = new GridViewTextBoxColumn();
            this.newButton = new RadButton();
            this.editButton = new RadButton();
            this.deleteButton = new RadButton();
            this.refreshButton = new RadButton();
            this.closeButton = new RadButton();
            this.statusLabel = new Label();
            ((System.ComponentModel.ISupportInitialize)this.grid).BeginInit();
            ((System.ComponentModel.ISupportInitialize)this.grid.MasterTemplate).BeginInit();
            this.SuspendLayout();

            this.heading.Name = "heading";
            this.heading.Location = new Point(14, 13);
            this.heading.Size = new Size(895, 29);
            this.heading.Font = new Font("Segoe UI Semibold", 11F);

            this.titleColumn.Name = "titleColumn";
            this.titleColumn.FieldName = "title";
            this.titleColumn.HeaderText = "Risk";
            this.titleColumn.Width = 198;

            this.categoryColumn.Name = "categoryColumn";
            this.categoryColumn.FieldName = "category";
            this.categoryColumn.HeaderText = "Category";
            this.categoryColumn.Width = 110;

            this.statusColumn.Name = "statusColumn";
            this.statusColumn.FieldName = "status_display";
            this.statusColumn.HeaderText = "Status";
            this.statusColumn.Width = 101;

            this.severityColumn.Name = "severityColumn";
            this.severityColumn.FieldName = "severity";
            this.severityColumn.HeaderText = "Severity";
            this.severityColumn.Width = 92;

            this.scoreColumn.Name = "scoreColumn";
            this.scoreColumn.FieldName = "risk_score";
            this.scoreColumn.HeaderText = "Score";
            this.scoreColumn.Width = 70;

            this.ownerColumn.Name = "ownerColumn";
            this.ownerColumn.FieldName = "owner_name";
            this.ownerColumn.HeaderText = "Owner";
            this.ownerColumn.Width = 155;

            this.taskColumn.Name = "taskColumn";
            this.taskColumn.FieldName = "linked_key";
            this.taskColumn.HeaderText = "Linked task";
            this.taskColumn.Width = 110;

            this.dueColumn.Name = "dueColumn";
            this.dueColumn.FieldName = "due_date";
            this.dueColumn.HeaderText = "Due";
            this.dueColumn.Width = 99;
            this.dueColumn.FormatString = "{0:d}";
            this.grid.Name = "grid";
            this.grid.Location = new Point(14, 91);
            this.grid.Size = new Size(960, 386);
            this.grid.AutoGenerateColumns = false;
            this.grid.ReadOnly = true;
            this.grid.MasterTemplate.AllowAddNewRow = false;
            this.grid.MasterTemplate.AllowDeleteRow = false;
            this.grid.MasterTemplate.AllowEditRow = false;
            this.grid.MasterTemplate.EnableFiltering = true;
            this.grid.MasterTemplate.ShowFilteringRow = true;
            this.grid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] {
                this.titleColumn, this.categoryColumn, this.statusColumn, this.severityColumn, this.scoreColumn, this.ownerColumn, this.taskColumn, this.dueColumn });
            this.grid.CurrentRowChanged += this.SelectionChanged;
            this.grid.CellDoubleClick += this.EditDoubleClicked;

            this.newButton.Name = "newButton";
            this.newButton.Text = "Add risk";
            this.newButton.Location = new Point(14, 48);
            this.newButton.Size = new Size(94, 29);
            this.newButton.Click += this.NewClicked;

            this.editButton.Name = "editButton";
            this.editButton.Text = "Edit risk";
            this.editButton.Location = new Point(117, 48);
            this.editButton.Size = new Size(94, 29);
            this.editButton.Click += this.EditClicked;

            this.deleteButton.Name = "deleteButton";
            this.deleteButton.Text = "Delete risk";
            this.deleteButton.Location = new Point(220, 48);
            this.deleteButton.Size = new Size(94, 29);
            this.deleteButton.Click += this.DeleteClicked;

            this.refreshButton.Name = "refreshButton";
            this.refreshButton.Text = "Refresh";
            this.refreshButton.Location = new Point(323, 48);
            this.refreshButton.Size = new Size(94, 29);
            this.refreshButton.Click += this.RefreshClicked;

            this.statusLabel.Name = "statusLabel";
            this.statusLabel.Location = new Point(14, 491);
            this.statusLabel.Size = new Size(846, 35);

            this.closeButton.Name = "closeButton";
            this.closeButton.Text = "Close";
            this.closeButton.Location = new Point(885, 491);
            this.closeButton.Size = new Size(89, 29);
            this.closeButton.DialogResult = DialogResult.Cancel;

            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.ClientSize = new Size(987, 533);
            this.Controls.AddRange(new Control[] {
                this.heading, this.grid, this.newButton, this.editButton, this.deleteButton, this.refreshButton, this.closeButton,
                this.statusLabel });
            this.Font = new Font("Segoe UI", 10F);
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.MaximizeBox = false;
            this.MinimizeBox = false;
            this.Name = "PmsRisksForm";
            this.StartPosition = FormStartPosition.CenterParent;
            this.Text = "Project risk register";
            this.CancelButton = this.closeButton;
            this.Load += this.RisksLoaded;
            ((System.ComponentModel.ISupportInitialize)this.grid.MasterTemplate).EndInit();
            ((System.ComponentModel.ISupportInitialize)this.grid).EndInit();
            this.ResumeLayout(false);
            this.PerformLayout();
        }

        private Label heading;
        private RadGridView grid;
        private GridViewTextBoxColumn titleColumn;
        private GridViewTextBoxColumn categoryColumn;
        private GridViewTextBoxColumn statusColumn;
        private GridViewTextBoxColumn severityColumn;
        private GridViewTextBoxColumn scoreColumn;
        private GridViewTextBoxColumn ownerColumn;
        private GridViewTextBoxColumn taskColumn;
        private GridViewTextBoxColumn dueColumn;
        private RadButton newButton;
        private RadButton editButton;
        private RadButton deleteButton;
        private RadButton refreshButton;
        private RadButton closeButton;
        private Label statusLabel;
    }
}
