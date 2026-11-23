#nullable disable
using System.Drawing;
using System.Windows.Forms;
using Telerik.WinControls.UI;

namespace Business_Suite
{
    partial class PmsWorkspaceRecoveryForm
    {
        private void InitializeComponent()
        {
            this.scopeLabel = new Label();
            this.grid = new RadGridView();
            this.nameColumn = new GridViewTextBoxColumn();
            this.ownersColumn = new GridViewTextBoxColumn();
            this.deletedColumn = new GridViewTextBoxColumn();
            this.restoredColumn = new GridViewTextBoxColumn();
            this.confirmationInput = new RadTextBox();
            this.resetButton = new RadButton();
            this.restoreButton = new RadButton();
            this.refreshButton = new RadButton();
            this.closeButton = new RadButton();
            this.statusLabel = new Label();
            ((System.ComponentModel.ISupportInitialize)this.grid).BeginInit();
            ((System.ComponentModel.ISupportInitialize)this.grid.MasterTemplate).BeginInit();
            this.SuspendLayout();

            this.scopeLabel.Name = "scopeLabel";
            this.scopeLabel.Text = "Reset archives all active workspaces in the selected company and branch. Each can be restored.";
            this.scopeLabel.Location = new Point(14, 12);
            this.scopeLabel.Size = new Size(764, 40);

            this.nameColumn.Name = "nameColumn";
            this.nameColumn.FieldName = "name";
            this.nameColumn.HeaderText = "Workspace";
            this.nameColumn.Width = 245;

            this.ownersColumn.Name = "ownersColumn";
            this.ownersColumn.FieldName = "owners";
            this.ownersColumn.HeaderText = "Owners";
            this.ownersColumn.Width = 242;

            this.deletedColumn.Name = "deletedColumn";
            this.deletedColumn.FieldName = "deleted_at";
            this.deletedColumn.HeaderText = "Archived (UTC)";
            this.deletedColumn.Width = 125;
            this.deletedColumn.FormatString = "{0:g}";

            this.restoredColumn.Name = "restoredColumn";
            this.restoredColumn.FieldName = "restored_at";
            this.restoredColumn.HeaderText = "Restored (UTC)";
            this.restoredColumn.Width = 125;
            this.restoredColumn.FormatString = "{0:g}";

            this.grid.Name = "grid";
            this.grid.Location = new Point(14, 57);
            this.grid.Size = new Size(764, 271);
            this.grid.AutoGenerateColumns = false;
            this.grid.ReadOnly = true;
            this.grid.MasterTemplate.AllowAddNewRow = false;
            this.grid.MasterTemplate.AllowDeleteRow = false;
            this.grid.MasterTemplate.AllowEditRow = false;
            this.grid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] {
                this.nameColumn, this.ownersColumn, this.deletedColumn, this.restoredColumn });
            this.grid.CurrentRowChanged += this.SelectionChanged;

            this.confirmationInput.Name = "confirmationInput";
            this.confirmationInput.NullText = "Type RESET ALL WORKSPACES";
            this.confirmationInput.Location = new Point(14, 348);
            this.confirmationInput.Size = new Size(253, 25);
            this.confirmationInput.TextChanged += this.ConfirmationChanged;

            this.resetButton.Name = "resetButton";
            this.resetButton.Text = "Reset active workspaces";
            this.resetButton.Location = new Point(278, 345);
            this.resetButton.Size = new Size(168, 29);
            this.resetButton.Click += this.ResetClicked;

            this.restoreButton.Name = "restoreButton";
            this.restoreButton.Text = "Restore selected";
            this.restoreButton.Location = new Point(457, 345);
            this.restoreButton.Size = new Size(125, 29);
            this.restoreButton.Click += this.RestoreClicked;

            this.refreshButton.Name = "refreshButton";
            this.refreshButton.Text = "Refresh preview";
            this.refreshButton.Location = new Point(594, 345);
            this.refreshButton.Size = new Size(123, 29);
            this.refreshButton.Click += this.RefreshClicked;

            this.statusLabel.Name = "statusLabel";
            this.statusLabel.Location = new Point(14, 386);
            this.statusLabel.Size = new Size(642, 45);

            this.closeButton.Name = "closeButton";
            this.closeButton.Text = "Close";
            this.closeButton.Location = new Point(690, 394);
            this.closeButton.Size = new Size(88, 28);
            this.closeButton.DialogResult = DialogResult.Cancel;

            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.ClientSize = new Size(795, 438);
            this.Controls.AddRange(new Control[] {
                this.scopeLabel, this.grid, this.confirmationInput, this.resetButton,
                this.restoreButton, this.refreshButton, this.statusLabel, this.closeButton });
            this.Font = new Font("Segoe UI", 10F);
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.MaximizeBox = false;
            this.MinimizeBox = false;
            this.Name = "PmsWorkspaceRecoveryForm";
            this.StartPosition = FormStartPosition.CenterParent;
            this.Text = "Workspace Recovery";
            this.CancelButton = this.closeButton;
            this.Load += this.RecoveryLoaded;
            ((System.ComponentModel.ISupportInitialize)this.grid.MasterTemplate).EndInit();
            ((System.ComponentModel.ISupportInitialize)this.grid).EndInit();
            this.ResumeLayout(false);
            this.PerformLayout();
        }

        private Label scopeLabel;
        private RadGridView grid;
        private GridViewTextBoxColumn nameColumn;
        private GridViewTextBoxColumn ownersColumn;
        private GridViewTextBoxColumn deletedColumn;
        private GridViewTextBoxColumn restoredColumn;
        private RadTextBox confirmationInput;
        private RadButton resetButton;
        private RadButton restoreButton;
        private RadButton refreshButton;
        private RadButton closeButton;
        private Label statusLabel;
    }
}
