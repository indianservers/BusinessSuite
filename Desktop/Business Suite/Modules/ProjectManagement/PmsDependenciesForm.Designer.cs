using Telerik.WinControls.UI;

namespace Business_Suite
{
    partial class PmsDependenciesForm
    {
        private void InitializeComponent()
        {
            this.heading = new Label();
            this.status = new Label();
            this.editor = new Panel();
            this.otherTaskLabel = new Label();
            this.directionLabel = new Label();
            this.kindLabel = new Label();
            this.lagLabel = new Label();
            this.confirmationLabel = new Label();
            this.confirmation = new Panel();
            this.grid = new RadGridView();
            this.otherTask = new RadDropDownList();
            this.direction = new RadDropDownList();
            this.kind = new RadDropDownList();
            this.lag = new RadTextBox();
            this.add = new RadButton();
            this.remove = new RadButton();
            this.refresh = new RadButton();
            this.close = new RadButton();
            this.confirm = new RadButton();
            this.cancel = new RadButton();
            this.predecessorColumn = new GridViewTextBoxColumn();
            this.successorColumn = new GridViewTextBoxColumn();
            this.typeColumn = new GridViewTextBoxColumn();
            this.lagColumn = new GridViewTextBoxColumn();
            this.conflictColumn = new GridViewCheckBoxColumn();
            ((System.ComponentModel.ISupportInitialize)this.grid).BeginInit();
            ((System.ComponentModel.ISupportInitialize)this.grid.MasterTemplate).BeginInit();
            this.SuspendLayout();
            this.heading.Name = "heading";
            this.heading.Location = new Point(13, 13);
            this.heading.Size = new Size(627, 27);
            this.heading.Font = new Font("Segoe UI Semibold", 11F);
            this.grid.Name = "grid";
            this.grid.Location = new Point(13, 50);
            this.grid.Size = new Size(762, 235);
            this.grid.ReadOnly = true;
            this.grid.AutoGenerateColumns = false;
            this.grid.MasterTemplate.AllowAddNewRow = false;
            this.grid.MasterTemplate.AllowDeleteRow = false;
            this.grid.MasterTemplate.AllowEditRow = false;
            this.grid.MasterTemplate.ShowRowHeaderColumn = false;
            this.grid.CurrentRowChanged += this.SelectionChanged;
            this.editor.Name = "editor";
            this.editor.Location = new Point(13, 297);
            this.editor.Size = new Size(762, 92);
            this.editor.Enabled = false;
            this.otherTaskLabel.Text = "Related task";
            this.otherTaskLabel.Location = new Point(0, 6);
            this.otherTaskLabel.Size = new Size(224, 20);
            this.otherTask.Name = "otherTask";
            this.otherTask.Location = new Point(0, 30);
            this.otherTask.Size = new Size(225, 27);
            this.otherTask.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
            this.otherTask.TextChanged += this.InputsChanged;
            this.directionLabel.Text = "Relationship";
            this.directionLabel.Location = new Point(239, 6);
            this.directionLabel.Size = new Size(157, 20);
            this.direction.Name = "direction";
            this.direction.Location = new Point(239, 30);
            this.direction.Size = new Size(157, 27);
            this.direction.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
            this.direction.Items.AddRange(new RadListDataItem[] {
                new RadListDataItem("Selected task depends on"), new RadListDataItem("Selected task blocks") });
            this.direction.SelectedIndex = 0;
            this.kindLabel.Text = "Dependency type";
            this.kindLabel.Location = new Point(409, 6);
            this.kindLabel.Size = new Size(145, 20);
            this.kind.Name = "kind";
            this.kind.Location = new Point(409, 30);
            this.kind.Size = new Size(145, 27);
            this.kind.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
            this.kind.Items.AddRange(new RadListDataItem[] {
                new RadListDataItem("Finish To Start"), new RadListDataItem("Start To Start"),
                new RadListDataItem("Finish To Finish"), new RadListDataItem("Start To Finish") });
            this.kind.SelectedIndex = 0;
            this.lagLabel.Text = "Lag days";
            this.lagLabel.Location = new Point(567, 6);
            this.lagLabel.Size = new Size(72, 20);
            this.lag.Name = "lag";
            this.lag.Location = new Point(567, 30);
            this.lag.Size = new Size(69, 27);
            this.lag.Text = "0";
            this.add.Name = "add";
            this.add.Text = "Add";
            this.add.Location = new Point(649, 29);
            this.add.Size = new Size(113, 29);
            this.add.Click += this.AddClicked;
            this.remove.Name = "remove";
            this.remove.Text = "Remove dependency";
            this.remove.Location = new Point(0, 63);
            this.remove.Size = new Size(165, 28);
            this.remove.Click += this.RemoveClicked;
            this.confirmation.Location = new Point(13, 398);
            this.confirmation.Size = new Size(762, 40);
            this.confirmation.Visible = false;
            this.confirmationLabel.Text = "Remove the selected dependency?";
            this.confirmationLabel.Location = new Point(0, 10);
            this.confirmationLabel.Size = new Size(463, 25);
            this.confirm.Name = "confirm";
            this.confirm.Text = "Remove";
            this.confirm.Location = new Point(486, 5);
            this.confirm.Size = new Size(91, 28);
            this.confirm.Click += this.ConfirmRemovalClicked;
            this.cancel.Name = "cancel";
            this.cancel.Text = "Cancel";
            this.cancel.Location = new Point(587, 5);
            this.cancel.Size = new Size(91, 28);
            this.cancel.Click += this.CancelRemovalClicked;
            this.status.Location = new Point(13, 449);
            this.status.Size = new Size(649, 31);
            this.refresh.Name = "refresh";
            this.refresh.Text = "Refresh";
            this.refresh.Location = new Point(680, 12);
            this.refresh.Size = new Size(95, 29);
            this.refresh.Click += this.RefreshClicked;
            this.close.Name = "close";
            this.close.Text = "Close";
            this.close.Location = new Point(680, 449);
            this.close.Size = new Size(95, 29);
            this.close.DialogResult = DialogResult.Cancel;
            this.predecessorColumn.Name = "predecessorColumn";
            this.predecessorColumn.FieldName = "predecessor";
            this.predecessorColumn.HeaderText = "Predecessor";
            this.predecessorColumn.Width = 230;
            this.successorColumn.Name = "successorColumn";
            this.successorColumn.FieldName = "successor";
            this.successorColumn.HeaderText = "Successor";
            this.successorColumn.Width = 230;
            this.typeColumn.Name = "typeColumn";
            this.typeColumn.FieldName = "dependency_type";
            this.typeColumn.HeaderText = "Type";
            this.typeColumn.Width = 131;
            this.lagColumn.Name = "lagColumn";
            this.lagColumn.FieldName = "lag_days";
            this.lagColumn.HeaderText = "Lag days";
            this.lagColumn.Width = 70;
            this.conflictColumn.Name = "conflictColumn";
            this.conflictColumn.FieldName = "date_conflict";
            this.conflictColumn.HeaderText = "Date conflict";
            this.conflictColumn.Width = 93;
            this.grid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] {
                this.predecessorColumn, this.successorColumn, this.typeColumn, this.lagColumn, this.conflictColumn });
            this.editor.Controls.AddRange(new Control[] {
                this.otherTaskLabel, this.otherTask, this.directionLabel, this.direction, this.kindLabel, this.kind,
                this.lagLabel, this.lag, this.add, this.remove });
            this.confirmation.Controls.AddRange(new Control[] { this.confirmationLabel, this.confirm, this.cancel });
            this.Controls.AddRange(new Control[] { this.heading, this.grid, this.editor, this.confirmation, this.status, this.refresh, this.close });
            this.CancelButton = this.close;
            this.AutoScaleMode = AutoScaleMode.Font;
            this.ClientSize = new Size(788, 496);
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.StartPosition = FormStartPosition.CenterParent;
            this.MinimizeBox = false;
            this.MaximizeBox = false;
            this.Text = "Task Dependencies";
            this.Load += this.DependenciesLoaded;
            ((System.ComponentModel.ISupportInitialize)this.grid.MasterTemplate).EndInit();
            ((System.ComponentModel.ISupportInitialize)this.grid).EndInit();
            this.ResumeLayout(false);
        }

        private Label heading, status, otherTaskLabel, directionLabel, kindLabel, lagLabel, confirmationLabel;
        private Panel editor, confirmation;
        private RadGridView grid;
        private RadDropDownList otherTask, direction, kind;
        private RadTextBox lag;
        private RadButton add, remove, refresh, close, confirm, cancel;
        private GridViewTextBoxColumn predecessorColumn, successorColumn, typeColumn, lagColumn;
        private GridViewCheckBoxColumn conflictColumn;
    }
}
