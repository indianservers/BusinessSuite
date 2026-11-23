using Telerik.WinControls.UI;

namespace Business_Suite
{
    partial class EmployeeSkillsForm
    {
        private void InitializeComponent()
        {
            this.heading = new Label();
            this.status = new Label();
            this.editor = new Panel();
            this.confirmation = new Panel();
            this.confirmationLabel = new Label();
            this.grid = new RadGridView();
            this.skillNameLabel = new Label();
            this.skillName = new RadTextBox();
            this.proficiencyLabel = new Label();
            this.proficiency = new RadTextBox();
            this.yearsLabel = new Label();
            this.years = new RadTextBox();
            this.column0 = new GridViewTextBoxColumn();
            this.column1 = new GridViewTextBoxColumn();
            this.column2 = new GridViewTextBoxColumn();
            this.newRecord = new RadButton();
            this.edit = new RadButton();
            this.delete = new RadButton();
            this.refresh = new RadButton();
            this.save = new RadButton();
            this.confirmDelete = new RadButton();
            this.cancelDelete = new RadButton();
            this.close = new RadButton();
            ((System.ComponentModel.ISupportInitialize)this.grid).BeginInit();
            ((System.ComponentModel.ISupportInitialize)this.grid.MasterTemplate).BeginInit();
            this.SuspendLayout();
            this.heading.Location = new Point(12, 12);
            this.heading.Size = new Size(740, 28);
            this.status.Location = new Point(12, 529);
            this.status.Size = new Size(645, 26);
            this.grid.Location = new Point(12, 45);
            this.grid.Size = new Size(744, 222);
            this.grid.ReadOnly = true;
            this.grid.Name = "skillsGrid";
            this.grid.MasterTemplate.AutoGenerateColumns = false;
            this.grid.MasterTemplate.AllowAddNewRow = false;
            this.grid.MasterTemplate.AllowDeleteRow = false;
            this.grid.MasterTemplate.AllowEditRow = false;
            this.grid.MasterTemplate.ShowRowHeaderColumn = false;
            this.grid.MasterTemplate.AutoSizeColumnsMode = GridViewAutoSizeColumnsMode.Fill;
            this.grid.CurrentRowChanged += this.SelectionChanged;
            this.editor.Location = new Point(12, 318);
            this.editor.Size = new Size(744, 151);
            this.editor.Enabled = false;
            this.confirmation.Location = new Point(12, 471);
            this.confirmation.Size = new Size(744, 45);
            this.confirmationLabel.Location = new Point(12, 10);
            this.confirmationLabel.Size = new Size(471, 26);
            this.confirmation.Visible = false;
            this.skillNameLabel.Text = "Skill Name *";
            this.skillNameLabel.Location = new Point(0, 0);
            this.skillNameLabel.Size = new Size(230, 20);
            this.skillName.Location = new Point(0, 21);
            this.skillName.Size = new Size(232, 25);
            this.skillName.Name = "skill_name";
            this.column0.Name = "skill_name";
            this.column0.FieldName = "skill_name";
            this.column0.HeaderText = "Skill Name";
            this.proficiencyLabel.Text = "Proficiency";
            this.proficiencyLabel.Location = new Point(248, 0);
            this.proficiencyLabel.Size = new Size(230, 20);
            this.proficiency.Location = new Point(248, 21);
            this.proficiency.Size = new Size(232, 25);
            this.proficiency.Name = "proficiency";
            this.column1.Name = "proficiency";
            this.column1.FieldName = "proficiency";
            this.column1.HeaderText = "Proficiency";
            this.column2.Name = "years_experience";
            this.column2.FieldName = "years_experience";
            this.column2.HeaderText = "Years Experience";
            this.yearsLabel.Text = "Years Experience";
            this.yearsLabel.Location = new Point(496, 0);
            this.yearsLabel.Size = new Size(230, 20);
            this.years.Location = new Point(496, 21);
            this.years.Size = new Size(232, 25);
            this.years.Name = "years";
            this.newRecord.Name = "newRecord";
            this.newRecord.Text = "New";
            this.newRecord.Location = new Point(12, 280);
            this.newRecord.Size = new Size(80, 28);
            this.newRecord.Click += this.NewClicked;
            this.edit.Name = "edit";
            this.edit.Text = "Edit";
            this.edit.Location = new Point(98, 280);
            this.edit.Size = new Size(80, 28);
            this.edit.Click += this.EditClicked;
            this.delete.Name = "delete";
            this.delete.Text = "Delete";
            this.delete.Location = new Point(184, 280);
            this.delete.Size = new Size(80, 28);
            this.delete.Click += this.AskDelete;
            this.refresh.Name = "refresh";
            this.refresh.Text = "Refresh";
            this.refresh.Location = new Point(270, 280);
            this.refresh.Size = new Size(80, 28);
            this.refresh.Click += this.RefreshClicked;
            this.save.Name = "save";
            this.save.Text = "Add skill";
            this.save.Location = new Point(607, 116);
            this.save.Size = new Size(130, 28);
            this.save.Click += this.SaveClicked;
            this.confirmDelete.Name = "confirmDelete";
            this.confirmDelete.Text = "Delete";
            this.confirmDelete.Location = new Point(492, 8);
            this.confirmDelete.Size = new Size(80, 28);
            this.confirmDelete.Click += this.ConfirmDelete;
            this.cancelDelete.Name = "cancelDelete";
            this.cancelDelete.Text = "Cancel";
            this.cancelDelete.Location = new Point(578, 8);
            this.cancelDelete.Size = new Size(80, 28);
            this.cancelDelete.Click += this.CancelDelete;
            this.close.Name = "close";
            this.close.Text = "Close";
            this.close.Location = new Point(669, 527);
            this.close.Size = new Size(80, 28);
            this.skillName.TextChanged += this.InputsChanged;
            this.close.DialogResult = DialogResult.Cancel;
            this.grid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] {
                this.column0, this.column1, this.column2 });
            this.editor.Controls.AddRange(new Control[] {
                this.skillNameLabel, this.skillName, this.proficiencyLabel, this.proficiency,

                this.yearsLabel, this.years, this.save });
            this.confirmation.Controls.AddRange(new Control[] {
                this.confirmationLabel, this.confirmDelete, this.cancelDelete });
            this.Controls.AddRange(new Control[] {
                this.heading, this.grid, this.newRecord, this.edit, this.delete, this.refresh,
                this.editor, this.confirmation, this.status, this.close });
            this.CancelButton = this.close;
            this.AutoScaleMode = AutoScaleMode.Font;
            this.ClientSize = new Size(768, 568);
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.MaximizeBox = false;
            this.MinimizeBox = false;
            this.StartPosition = FormStartPosition.CenterParent;
            this.Text = "Employee Skills";
            this.Load += this.Loaded;
            ((System.ComponentModel.ISupportInitialize)this.grid.MasterTemplate).EndInit();
            ((System.ComponentModel.ISupportInitialize)this.grid).EndInit();
            this.ResumeLayout(false);
        }

        private Label heading, status, confirmationLabel;
        private Panel editor, confirmation;
        private RadGridView grid;
        private GridViewTextBoxColumn column0, column1, column2;
        private Label skillNameLabel, proficiencyLabel, yearsLabel;
        private RadTextBox skillName, proficiency, years;
        private RadButton newRecord, edit, delete, refresh, save, confirmDelete, cancelDelete, close;
    }
}

