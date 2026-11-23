#nullable disable
using System.Drawing;
using System.Windows.Forms;
using Telerik.WinControls.UI;

namespace Business_Suite
{
    partial class EmployeeAdministrationForm
    {
        private void InitializeComponent()
        {
            this.toolbar = new Panel();
            this.searchInput = new RadTextBox();
            this.searchButton = new RadButton();
            this.editButton = new RadButton();
            this.lifecycleButton = new RadButton();
            this.archiveButton = new RadButton();
            this.educationButton = new RadButton();
            this.skillsButton = new RadButton();
            this.experienceButton = new RadButton();
            this.certificationButton = new RadButton();
            this.historyButton = new RadButton();
            this.checksButton = new RadButton();
            this.quickAddButton = new RadButton();
            this.documentsButton = new RadButton();
            this.split = new SplitContainer();
            this.employeeGrid = new RadGridView();
            this.editor = new Panel();
            this.selectedLabel = new Label();
            this.idColumn = new GridViewTextBoxColumn();
            this.nameColumn = new GridViewTextBoxColumn();
            this.displayColumn = new GridViewTextBoxColumn();
            this.statusColumn = new GridViewTextBoxColumn();
            this.locationColumn = new GridViewTextBoxColumn();
            this.displayLabel = new Label();
            this.displayInput = new RadTextBox();
            this.locationLabel = new Label();
            this.locationInput = new RadDropDownList();
            this.extensionLabel = new Label();
            this.extensionInput = new RadTextBox();
            this.deskLabel = new Label();
            this.deskInput = new RadTextBox();
            this.visibilityLabel = new Label();
            this.visibilityInput = new RadDropDownList();
            this.saveButton = new RadButton();
            this.cancelButton = new RadButton();
            this.statusLabel = new Label();
            ((System.ComponentModel.ISupportInitialize)this.employeeGrid).BeginInit();
            ((System.ComponentModel.ISupportInitialize)this.employeeGrid.MasterTemplate).BeginInit();
            ((System.ComponentModel.ISupportInitialize)this.split).BeginInit();
            this.split.Panel1.SuspendLayout();
            this.split.Panel2.SuspendLayout();
            this.split.SuspendLayout();
            this.toolbar.SuspendLayout();
            this.editor.SuspendLayout();
            this.SuspendLayout();

            this.searchInput.Name = "searchInput";
            this.searchInput.Location = new Point(11, 11);
            this.searchInput.Size = new Size(230, 25);
            this.searchInput.NullText = "Employee name or ID";
            this.searchInput.KeyDown += this.SearchKeyDown;

            this.searchButton.Name = "searchButton";
            this.searchButton.Text = "Search";
            this.searchButton.Location = new Point(252, 9);
            this.searchButton.Size = new Size(88, 28);
            this.searchButton.Click += this.SearchClicked;

            this.editButton.Name = "editButton";
            this.editButton.Text = "Edit profile";
            this.editButton.Location = new Point(352, 9);
            this.editButton.Size = new Size(105, 28);
            this.editButton.Click += this.EditClicked;
            this.editButton.Enabled = false;

            this.lifecycleButton.Name = "lifecycleButton";
            this.lifecycleButton.Text = "Lifecycle";
            this.lifecycleButton.Location = new Point(468, 9);
            this.lifecycleButton.Size = new Size(94, 28);
            this.lifecycleButton.Enabled = false;
            this.lifecycleButton.Click += this.LifecycleClicked;
            this.archiveButton.Name = "archiveButton";
            this.archiveButton.Text = "Archive";
            this.archiveButton.Location = new Point(573, 9);
            this.archiveButton.Size = new Size(94, 28);
            this.archiveButton.Enabled = false;
            this.archiveButton.Click += this.ArchiveClicked;
            this.educationButton.Name = "educationButton";
            this.educationButton.Text = "Education";
            this.educationButton.Location = new Point(10, 45);
            this.educationButton.Size = new Size(94, 28);
            this.educationButton.Enabled = false;
            this.educationButton.Click += this.EducationClicked;
            this.skillsButton.Name = "skillsButton";
            this.skillsButton.Text = "Skills";
            this.skillsButton.Location = new Point(114, 45);
            this.skillsButton.Size = new Size(94, 28);
            this.skillsButton.Enabled = false;
            this.skillsButton.Click += this.SkillsClicked;
            this.experienceButton.Name = "experienceButton";
            this.experienceButton.Text = "Experience";
            this.experienceButton.Location = new Point(218, 45);
            this.experienceButton.Size = new Size(106, 28);
            this.experienceButton.Enabled = false;
            this.experienceButton.Click += this.ExperienceClicked;
            this.certificationButton.Name = "certificationButton";
            this.certificationButton.Text = "Certifications";
            this.certificationButton.Location = new Point(334, 45);
            this.certificationButton.Size = new Size(117, 28);
            this.certificationButton.Enabled = false;
            this.certificationButton.Click += this.CertificationsClicked;
            this.historyButton.Name = "historyButton";
            this.historyButton.Text = "Profile History";
            this.historyButton.Location = new Point(461, 45);
            this.historyButton.Size = new Size(120, 28);
            this.historyButton.Enabled = false;
            this.historyButton.Click += this.HistoryClicked;
            this.checksButton.Name = "checksButton";
            this.checksButton.Text = "Profile Checks";
            this.checksButton.Location = new Point(591, 45);
            this.checksButton.Size = new Size(110, 28);
            this.checksButton.Enabled = false;
            this.checksButton.Click += this.ChecksClicked;
            this.quickAddButton.Name = "quickAddButton";
            this.quickAddButton.Text = "Quick Add Employee";
            this.quickAddButton.Location = new Point(678, 9);
            this.quickAddButton.Size = new Size(143, 28);
            this.quickAddButton.Click += this.QuickAddClicked;
            this.documentsButton.Name = "documentsButton";
            this.documentsButton.Text = "Documents";
            this.documentsButton.Location = new Point(711, 45);
            this.documentsButton.Size = new Size(110, 28);
            this.documentsButton.Enabled = false;
            this.documentsButton.Click += this.DocumentsClicked;

            this.toolbar.Name = "toolbar";
            this.toolbar.Dock = DockStyle.Top;
            this.toolbar.Height = 83;
            this.toolbar.Controls.AddRange(new Control[] {
                this.searchInput, this.searchButton, this.editButton, this.lifecycleButton, this.archiveButton, this.educationButton, this.skillsButton, this.experienceButton, this.certificationButton, this.historyButton, this.checksButton, this.quickAddButton, this.documentsButton });

            this.idColumn.Name = "idColumn";
            this.idColumn.FieldName = "employee_id";
            this.idColumn.HeaderText = "Employee ID";
            this.idColumn.Width = 107;

            this.nameColumn.Name = "nameColumn";
            this.nameColumn.FieldName = "employee_name";
            this.nameColumn.HeaderText = "Employee";
            this.nameColumn.Width = 198;

            this.displayColumn.Name = "displayColumn";
            this.displayColumn.FieldName = "preferred_display_name";
            this.displayColumn.HeaderText = "Display name";
            this.displayColumn.Width = 172;

            this.statusColumn.Name = "statusColumn";
            this.statusColumn.FieldName = "status";
            this.statusColumn.HeaderText = "Status";
            this.statusColumn.Width = 98;

            this.locationColumn.Name = "locationColumn";
            this.locationColumn.FieldName = "work_location";
            this.locationColumn.HeaderText = "Work location";
            this.locationColumn.Width = 115;

            this.employeeGrid.Name = "employeeGrid";
            this.employeeGrid.Dock = DockStyle.Fill;
            this.employeeGrid.AutoGenerateColumns = false;
            this.employeeGrid.ReadOnly = true;
            this.employeeGrid.MasterTemplate.AllowAddNewRow = false;
            this.employeeGrid.MasterTemplate.AllowDeleteRow = false;
            this.employeeGrid.MasterTemplate.AllowEditRow = false;
            this.employeeGrid.MasterTemplate.EnableFiltering = true;
            this.employeeGrid.MasterTemplate.ShowFilteringRow = true;
            this.employeeGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] {
                this.idColumn, this.nameColumn, this.displayColumn, this.statusColumn, this.locationColumn });
            this.employeeGrid.CurrentRowChanged += this.EmployeeSelectionChanged;
            this.employeeGrid.CellDoubleClick += this.EmployeeDoubleClicked;

            this.selectedLabel.Name = "selectedLabel";
            this.selectedLabel.Location = new Point(15, 13);
            this.selectedLabel.Size = new Size(300, 28);
            this.selectedLabel.Font = new Font("Segoe UI Semibold", 11F);

            this.displayLabel.Name = "displayLabel";
            this.displayLabel.Text = "Preferred display name";
            this.displayLabel.Location = new Point(15, 49);
            this.displayLabel.Size = new Size(275, 22);
            this.displayInput.Name = "displayInput";
            this.displayInput.Location = new Point(15, 71);
            this.displayInput.Size = new Size(294, 25);
            this.displayInput.TabIndex = 0;
            this.displayInput.MaxLength = 500;

            this.locationLabel.Name = "locationLabel";
            this.locationLabel.Text = "Work location";
            this.locationLabel.Location = new Point(15, 106);
            this.locationLabel.Size = new Size(275, 22);
            this.locationInput.Name = "locationInput";
            this.locationInput.Location = new Point(15, 128);
            this.locationInput.Size = new Size(294, 25);
            this.locationInput.TabIndex = 1;

            this.extensionLabel.Name = "extensionLabel";
            this.extensionLabel.Text = "Office extension";
            this.extensionLabel.Location = new Point(15, 163);
            this.extensionLabel.Size = new Size(275, 22);
            this.extensionInput.Name = "extensionInput";
            this.extensionInput.Location = new Point(15, 185);
            this.extensionInput.Size = new Size(294, 25);
            this.extensionInput.TabIndex = 2;
            this.extensionInput.MaxLength = 60;

            this.deskLabel.Name = "deskLabel";
            this.deskLabel.Text = "Desk code";
            this.deskLabel.Location = new Point(15, 220);
            this.deskLabel.Size = new Size(275, 22);
            this.deskInput.Name = "deskInput";
            this.deskInput.Location = new Point(15, 242);
            this.deskInput.Size = new Size(294, 25);
            this.deskInput.TabIndex = 3;
            this.deskInput.MaxLength = 100;

            this.visibilityLabel.Name = "visibilityLabel";
            this.visibilityLabel.Text = "Directory visibility";
            this.visibilityLabel.Location = new Point(15, 277);
            this.visibilityLabel.Size = new Size(275, 22);
            this.visibilityInput.Name = "visibilityInput";
            this.visibilityInput.Location = new Point(15, 299);
            this.visibilityInput.Size = new Size(294, 25);
            this.visibilityInput.TabIndex = 4;

            this.locationInput.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
            this.locationInput.Items.AddRange(new RadListDataItem[] {
                new RadListDataItem("Office") { Value = "Office" }, new RadListDataItem("Remote") { Value = "Remote" },
                new RadListDataItem("Hybrid") { Value = "Hybrid" }, new RadListDataItem("Field") { Value = "Field" },
                new RadListDataItem("On-Site") { Value = "On-Site" }, new RadListDataItem("Unspecified") });
            this.visibilityInput.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
            this.visibilityInput.Items.AddRange(new RadListDataItem[] {
                new RadListDataItem("Public") { Value = "public" }, new RadListDataItem("Team") { Value = "team" },
                new RadListDataItem("Hidden") { Value = "hidden" } });

            this.saveButton.Name = "saveButton";
            this.saveButton.Text = "Save";
            this.saveButton.Location = new Point(125, 347);
            this.saveButton.Size = new Size(85, 29);
            this.saveButton.Click += this.SaveClicked;

            this.cancelButton.Name = "cancelButton";
            this.cancelButton.Text = "Cancel";
            this.cancelButton.Location = new Point(224, 347);
            this.cancelButton.Size = new Size(85, 29);
            this.cancelButton.Click += this.CancelClicked;

            this.editor.Name = "editor";
            this.editor.Dock = DockStyle.Fill;
            this.editor.Enabled = false;
            this.editor.Controls.AddRange(new Control[] {
                this.selectedLabel, this.displayLabel, this.displayInput,
                this.locationLabel, this.locationInput,
                this.extensionLabel, this.extensionInput,
                this.deskLabel, this.deskInput,
                this.visibilityLabel, this.visibilityInput,
                this.saveButton, this.cancelButton });

            this.split.Name = "split";
            this.split.Dock = DockStyle.Fill;
            this.split.FixedPanel = FixedPanel.Panel2;
            this.split.Size = new Size(1047, 521);
            this.split.SplitterDistance = 720;
            this.split.Panel1MinSize = 330;
            this.split.Panel2MinSize = 322;
            this.split.Panel1.Controls.Add(this.employeeGrid);
            this.split.Panel2.Controls.Add(this.editor);

            this.statusLabel.Name = "statusLabel";
            this.statusLabel.Dock = DockStyle.Bottom;
            this.statusLabel.Height = 30;
            this.statusLabel.Padding = new Padding(10, 5, 10, 0);

            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.ClientSize = new Size(1047, 600);
            this.MinimumSize = new Size(850, 510);
            this.Controls.Add(this.split);
            this.Controls.Add(this.statusLabel);
            this.Controls.Add(this.toolbar);
            this.Font = new Font("Segoe UI", 10F);
            this.Name = "EmployeeAdministrationForm";
            this.StartPosition = FormStartPosition.CenterParent;
            this.Text = "Business Suite | Employee Administration";
            this.Load += this.EmployeeAdministrationLoaded;
            ((System.ComponentModel.ISupportInitialize)this.employeeGrid.MasterTemplate).EndInit();
            ((System.ComponentModel.ISupportInitialize)this.employeeGrid).EndInit();
            ((System.ComponentModel.ISupportInitialize)this.split).EndInit();
            this.split.Panel1.ResumeLayout(false);
            this.split.Panel2.ResumeLayout(false);
            this.split.ResumeLayout(false);
            this.toolbar.ResumeLayout(false);
            this.toolbar.PerformLayout();
            this.editor.ResumeLayout(false);
            this.editor.PerformLayout();
            this.ResumeLayout(false);
        }

        private Panel toolbar;
        private RadTextBox searchInput;
        private RadButton searchButton;
        private RadButton editButton;
        private RadButton lifecycleButton;
        private RadButton archiveButton;
        private RadButton educationButton;
        private RadButton skillsButton;
        private RadButton experienceButton;
        private RadButton certificationButton;
        private RadButton historyButton;
        private RadButton checksButton;
        private RadButton quickAddButton;
        private RadButton documentsButton;
        private SplitContainer split;
        private RadGridView employeeGrid;
        private Panel editor;
        private Label selectedLabel;
        private GridViewTextBoxColumn idColumn;
        private GridViewTextBoxColumn nameColumn;
        private GridViewTextBoxColumn displayColumn;
        private GridViewTextBoxColumn statusColumn;
        private GridViewTextBoxColumn locationColumn;
        private Label displayLabel;
        private RadTextBox displayInput;
        private Label locationLabel;
        private RadDropDownList locationInput;
        private Label extensionLabel;
        private RadTextBox extensionInput;
        private Label deskLabel;
        private RadTextBox deskInput;
        private Label visibilityLabel;
        private RadDropDownList visibilityInput;
        private RadButton saveButton;
        private RadButton cancelButton;
        private Label statusLabel;
    }
}
