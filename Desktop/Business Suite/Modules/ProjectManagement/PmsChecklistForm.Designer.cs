#nullable disable
using System.Drawing;
using System.Windows.Forms;
using Telerik.WinControls.UI;

namespace Business_Suite
{
    partial class PmsChecklistForm
    {
        private void InitializeComponent()
        {
            this.heading = new Label();
            this.grid = new RadGridView();
            this.titleColumn = new GridViewTextBoxColumn();
            this.completeColumn = new GridViewCheckBoxColumn();
            this.newInput = new RadTextBox();
            this.nameInput = new RadTextBox();
            this.addButton = new RadButton();
            this.renameButton = new RadButton();
            this.toggleButton = new RadButton();
            this.deleteButton = new RadButton();
            this.upButton = new RadButton();
            this.downButton = new RadButton();
            this.closeButton = new RadButton();
            this.refreshButton = new RadButton();
            this.statusLabel = new Label();
            ((System.ComponentModel.ISupportInitialize)this.grid).BeginInit();
            ((System.ComponentModel.ISupportInitialize)this.grid.MasterTemplate).BeginInit();
            this.SuspendLayout();

            this.heading.Name = "heading";
            this.heading.Location = new Point(14, 12);
            this.heading.Size = new Size(676, 28);
            this.heading.Font = new Font("Segoe UI Semibold", 11F);

            this.titleColumn.Name = "titleColumn";
            this.titleColumn.FieldName = "title";
            this.titleColumn.HeaderText = "Checklist item";
            this.titleColumn.AllowSort = false;
            this.titleColumn.Width = 540;
            this.completeColumn.Name = "completeColumn";
            this.completeColumn.FieldName = "is_completed";
            this.completeColumn.HeaderText = "Completed";
            this.completeColumn.AllowSort = false;
            this.completeColumn.Width = 110;

            this.grid.Name = "grid";
            this.grid.Location = new Point(14, 49);
            this.grid.Size = new Size(676, 279);
            this.grid.AutoGenerateColumns = false;
            this.grid.ReadOnly = true;
            this.grid.MasterTemplate.AllowAddNewRow = false;
            this.grid.MasterTemplate.AllowDeleteRow = false;
            this.grid.MasterTemplate.AllowEditRow = false;
            this.grid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] {
                this.titleColumn, this.completeColumn });
            this.grid.CurrentRowChanged += this.SelectionChanged;

            this.newInput.Name = "newInput";
            this.newInput.NullText = "New checklist item";
            this.newInput.Location = new Point(14, 345);
            this.newInput.Size = new Size(415, 25);
            this.newInput.MaxLength = 220;
            this.newInput.TextChanged += this.InputChanged;

            this.nameInput.Name = "nameInput";
            this.nameInput.NullText = "Selected checklist item";
            this.nameInput.Location = new Point(14, 386);
            this.nameInput.Size = new Size(408, 25);
            this.nameInput.MaxLength = 220;
            this.nameInput.TextChanged += this.InputChanged;

            this.addButton.Name = "addButton";
            this.addButton.Text = "Add item";
            this.addButton.Location = new Point(440, 342);
            this.addButton.Size = new Size(88, 28);
            this.addButton.Click += this.AddClicked;

            this.renameButton.Name = "renameButton";
            this.renameButton.Text = "Rename";
            this.renameButton.Location = new Point(432, 383);
            this.renameButton.Size = new Size(84, 28);
            this.renameButton.Click += this.RenameClicked;

            this.toggleButton.Name = "toggleButton";
            this.toggleButton.Text = "Complete";
            this.toggleButton.Location = new Point(522, 383);
            this.toggleButton.Size = new Size(85, 28);
            this.toggleButton.Click += this.ToggleClicked;

            this.deleteButton.Name = "deleteButton";
            this.deleteButton.Text = "Delete";
            this.deleteButton.Location = new Point(613, 383);
            this.deleteButton.Size = new Size(78, 28);
            this.deleteButton.Click += this.DeleteClicked;

            this.upButton.Name = "upButton";
            this.upButton.Text = "Move up";
            this.upButton.Location = new Point(507, 423);
            this.upButton.Size = new Size(86, 28);
            this.upButton.Click += this.UpClicked;

            this.downButton.Name = "downButton";
            this.downButton.Text = "Move down";
            this.downButton.Location = new Point(599, 423);
            this.downButton.Size = new Size(92, 28);
            this.downButton.Click += this.DownClicked;

            this.closeButton.Name = "closeButton";
            this.closeButton.Text = "Close";
            this.closeButton.Location = new Point(602, 466);
            this.closeButton.Size = new Size(89, 28);
            this.closeButton.DialogResult = DialogResult.Cancel;

            this.refreshButton.Name = "refreshButton";
            this.refreshButton.Text = "Refresh";
            this.refreshButton.Location = new Point(538, 342);
            this.refreshButton.Size = new Size(86, 28);
            this.refreshButton.Click += this.RefreshClicked;

            this.statusLabel.Name = "statusLabel";
            this.statusLabel.Location = new Point(14, 451);
            this.statusLabel.Size = new Size(570, 44);

            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.ClientSize = new Size(706, 508);
            this.Controls.AddRange(new Control[] {
                this.heading, this.grid, this.newInput, this.nameInput, this.addButton, this.renameButton, this.toggleButton, this.deleteButton, this.upButton, this.downButton,
                this.statusLabel, this.closeButton, this.refreshButton });
            this.Font = new Font("Segoe UI", 10F);
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.MaximizeBox = false;
            this.MinimizeBox = false;
            this.Name = "PmsChecklistForm";
            this.StartPosition = FormStartPosition.CenterParent;
            this.Text = "Task checklist";
            this.CancelButton = this.closeButton;
            this.Load += this.ChecklistLoaded;
            ((System.ComponentModel.ISupportInitialize)this.grid.MasterTemplate).EndInit();
            ((System.ComponentModel.ISupportInitialize)this.grid).EndInit();
            this.ResumeLayout(false);
            this.PerformLayout();
        }

        private Label heading;
        private RadGridView grid;
        private GridViewTextBoxColumn titleColumn;
        private GridViewCheckBoxColumn completeColumn;
        private RadTextBox newInput;
        private RadTextBox nameInput;
        private RadButton addButton;
        private RadButton renameButton;
        private RadButton toggleButton;
        private RadButton deleteButton;
        private RadButton upButton;
        private RadButton downButton;
        private Label statusLabel;
        private RadButton closeButton;
        private RadButton refreshButton;
    }
}
