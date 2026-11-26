#nullable disable
using System;
using System.Drawing;
using System.Windows.Forms;
using Telerik.WinControls.UI;

namespace Business_Suite
{
    partial class CrmDirectoryForm
    {
        private void InitializeComponent()
        {
            this.newButton = new Button();
            this.editButton = new Button();
            this.archiveButton = new Button();
            this.restoreButton = new Button();
            this.viewButton = new Button();
            this.exportButton = new Button();
            this.exportDialog = new SaveFileDialog();
            this.gridMenu = new ContextMenuStrip();
            this.copyRowMenuItem = new ToolStripMenuItem();
            this.titleLabel = new Label();
            this.searchBox = new CueTextBox();
            this.roleFilter = new ComboBox();
            this.archivedCheck = new CheckBox();
            this.searchButton = new Button();
            this.refreshButton = new Button();
            this.grid = new RadGridView();
            this.nameColumn = new GridViewTextBoxColumn();
            this.classificationColumn = new GridViewTextBoxColumn();
            this.contextColumn = new GridViewTextBoxColumn();
            this.emailColumn = new GridViewTextBoxColumn();
            this.phoneColumn = new GridViewTextBoxColumn();
            this.cityColumn = new GridViewTextBoxColumn();
            this.countryColumn = new GridViewTextBoxColumn();
            this.statusColumn = new GridViewTextBoxColumn();
            this.statusLabel = new Label();
            this.previousButton = new Button();
            this.nextButton = new Button();
            ((System.ComponentModel.ISupportInitialize)this.grid).BeginInit();
            ((System.ComponentModel.ISupportInitialize)this.grid.MasterTemplate).BeginInit();
            this.SuspendLayout();
            this.newButton.Location = new Point(718, 25);
            this.newButton.Size = new Size(100, 37);
            this.newButton.Anchor = AnchorStyles.Top | AnchorStyles.Right;
            this.newButton.Name = "newButton";
            this.newButton.Text = "New";
            this.newButton.Enabled = false;
            this.newButton.Click += this.NewClicked;
            this.Controls.Add(this.newButton);
            this.editButton.Location = new Point(824, 25);
            this.editButton.Size = new Size(100, 37);
            this.editButton.Anchor = AnchorStyles.Top | AnchorStyles.Right;
            this.editButton.Name = "editButton";
            this.editButton.Text = "Edit";
            this.editButton.Enabled = false;
            this.editButton.Click += this.EditClicked;
            this.Controls.Add(this.editButton);
            this.archiveButton.Location = new Point(930, 25);
            this.archiveButton.Size = new Size(100, 37);
            this.archiveButton.Anchor = AnchorStyles.Top | AnchorStyles.Right;
            this.archiveButton.Name = "archiveButton";
            this.archiveButton.Text = "Archive";
            this.archiveButton.Enabled = false;
            this.archiveButton.Click += this.ArchiveClicked;
            this.Controls.Add(this.archiveButton);
            this.restoreButton.Location = new Point(1036, 25);
            this.restoreButton.Size = new Size(100, 37);
            this.restoreButton.Anchor = AnchorStyles.Top | AnchorStyles.Right;
            this.restoreButton.Name = "restoreButton";
            this.restoreButton.Text = "Restore";
            this.restoreButton.Enabled = false;
            this.restoreButton.Click += this.RestoreClicked;
            this.Controls.Add(this.restoreButton);
            this.grid.SelectionChanged += this.RecordSelectionChanged;
            this.viewButton.Location = new Point(877, 80);
            this.viewButton.Size = new Size(111, 34);
            this.viewButton.Name = "viewButton";
            this.viewButton.Text = "View record";
            this.viewButton.Click += this.ViewClicked;
            this.Controls.Add(this.viewButton);
            this.exportButton.Location = new Point(997, 80);
            this.exportButton.Size = new Size(139, 34);
            this.exportButton.Anchor = AnchorStyles.Top | AnchorStyles.Right;
            this.exportButton.Name = "exportButton";
            this.exportButton.Text = "Export CSV";
            this.exportButton.Enabled = false;
            this.exportButton.Click += this.ExportClicked;
            this.Controls.Add(this.exportButton);
            this.exportDialog.DefaultExt = "csv";
            this.exportDialog.Filter = "CSV files (*.csv)|*.csv";
            this.exportDialog.OverwritePrompt = true;
            this.exportDialog.RestoreDirectory = true;
            this.exportDialog.Title = "Export directory";
            this.exportDialog.RestoreDirectory = true;
            this.copyRowMenuItem.Name = "copyRowMenuItem";
            this.copyRowMenuItem.Text = "Copy selected row";
            this.copyRowMenuItem.Click += this.CopySelectedRowClicked;
            this.gridMenu.Items.AddRange(new ToolStripItem[] { this.copyRowMenuItem });
            // titleLabel
            this.titleLabel.Location = new Point(24, 20);
            this.titleLabel.Size = new Size(460, 50);
            this.titleLabel.Name = "titleLabel";
            this.titleLabel.Text = "Companies";
            this.titleLabel.Font = new Font("Segoe UI Semibold", 26F);
            // searchBox
            this.searchBox.Location = new Point(24, 83);
            this.searchBox.Size = new Size(340, 30);
            this.searchBox.Name = "searchBox";
            this.searchBox.PlaceholderText = "Search name, email or phone";
            this.searchBox.AccessibleName = "Search records";
            this.searchBox.MaxLength = 180;
            // roleFilter
            this.roleFilter.Location = new Point(377, 83);
            this.roleFilter.Size = new Size(146, 30);
            this.roleFilter.Name = "roleFilter";
            this.roleFilter.DropDownStyle = ComboBoxStyle.DropDownList;
            this.roleFilter.AccessibleName = "Relationship type";
            this.roleFilter.SelectedIndexChanged += this.FiltersChanged;
            // archivedCheck
            this.archivedCheck.Location = new Point(538, 83);
            this.archivedCheck.Size = new Size(122, 30);
            this.archivedCheck.Name = "archivedCheck";
            this.archivedCheck.Text = "Archived";
            this.archivedCheck.CheckedChanged += this.FiltersChanged;
            // searchButton
            this.searchButton.Location = new Point(673, 80);
            this.searchButton.Size = new Size(92, 34);
            this.searchButton.Name = "searchButton";
            this.searchButton.Text = "Search";
            this.searchButton.Click += this.FiltersChanged;
            // refreshButton
            this.refreshButton.Location = new Point(775, 80);
            this.refreshButton.Size = new Size(92, 34);
            this.refreshButton.Name = "refreshButton";
            this.refreshButton.Text = "Refresh";
            this.refreshButton.Click += this.RefreshClicked;
            // grid
            this.grid.Location = new Point(24, 130);
            this.grid.Size = new Size(1112, 435);
            this.grid.Name = "grid";
            this.grid.Anchor = AnchorStyles.Top | AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
            this.grid.MasterTemplate.AllowAddNewRow = false;
            this.grid.MasterTemplate.AllowDeleteRow = false;
            this.grid.MasterTemplate.AutoGenerateColumns = false;
            this.grid.MasterTemplate.AutoSizeColumnsMode = GridViewAutoSizeColumnsMode.Fill;
            this.grid.ReadOnly = true;
            this.grid.ShowGroupPanel = false;
            this.grid.ContextMenuStrip = this.gridMenu;
            // nameColumn
            this.nameColumn.Name = "name";
            this.nameColumn.FieldName = "name";
            this.nameColumn.HeaderText = "Name";
            this.nameColumn.Width = 180;
            // classificationColumn
            this.classificationColumn.Name = "classification";
            this.classificationColumn.FieldName = "classification";
            this.classificationColumn.HeaderText = "Relationship";
            this.classificationColumn.Width = 110;
            // contextColumn
            this.contextColumn.Name = "context";
            this.contextColumn.FieldName = "context";
            this.contextColumn.HeaderText = "Industry";
            this.contextColumn.Width = 150;
            // emailColumn
            this.emailColumn.Name = "email";
            this.emailColumn.FieldName = "email";
            this.emailColumn.HeaderText = "Email";
            this.emailColumn.Width = 170;
            // phoneColumn
            this.phoneColumn.Name = "phone";
            this.phoneColumn.FieldName = "phone_display";
            this.phoneColumn.HeaderText = "Phone";
            this.phoneColumn.Width = 135;
            // cityColumn
            this.cityColumn.Name = "city";
            this.cityColumn.FieldName = "city";
            this.cityColumn.HeaderText = "City";
            this.cityColumn.Width = 90;
            // countryColumn
            this.countryColumn.Name = "country";
            this.countryColumn.FieldName = "country";
            this.countryColumn.HeaderText = "Country";
            this.countryColumn.Width = 90;
            // statusColumn
            this.statusColumn.Name = "status";
            this.statusColumn.FieldName = "status";
            this.statusColumn.HeaderText = "Status";
            this.statusColumn.Width = 75;
            // statusLabel
            this.statusLabel.Location = new Point(24, 575);
            this.statusLabel.Size = new Size(792, 34);
            this.statusLabel.Name = "statusLabel";
            this.statusLabel.TextAlign = ContentAlignment.MiddleLeft;
            this.statusLabel.Anchor = AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
            // previousButton
            this.previousButton.Location = new Point(945, 575);
            this.previousButton.Size = new Size(90, 34);
            this.previousButton.Name = "previousButton";
            this.previousButton.Text = "Previous";
            this.previousButton.Enabled = false;
            this.previousButton.Anchor = AnchorStyles.Bottom | AnchorStyles.Right;
            this.previousButton.Click += this.PreviousClicked;
            // nextButton
            this.nextButton.Location = new Point(1046, 575);
            this.nextButton.Size = new Size(90, 34);
            this.nextButton.Name = "nextButton";
            this.nextButton.Text = "Next";
            this.nextButton.Enabled = false;
            this.nextButton.Anchor = AnchorStyles.Bottom | AnchorStyles.Right;
            this.nextButton.Click += this.NextClicked;
            this.roleFilter.Items.AddRange(new object[] { "All relationships", "Customer", "Prospect", "Vendor", "Partner" });
            this.grid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] { this.nameColumn, this.classificationColumn, this.contextColumn, this.emailColumn, this.phoneColumn, this.cityColumn, this.countryColumn, this.statusColumn });
            this.Shown += this.DirectoryShown;
            this.FormClosed += this.DirectoryClosed;
            this.Controls.Add(this.titleLabel);
            this.Controls.Add(this.searchBox);
            this.Controls.Add(this.roleFilter);
            this.Controls.Add(this.archivedCheck);
            this.Controls.Add(this.searchButton);
            this.Controls.Add(this.refreshButton);
            this.Controls.Add(this.grid);
            this.Controls.Add(this.statusLabel);
            this.Controls.Add(this.previousButton);
            this.Controls.Add(this.nextButton);
            this.AutoScaleDimensions = new SizeF(96F, 96F);
            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.Font = new Font("Segoe UI", 10F);
            this.BackColor = Color.FromArgb(243, 246, 251);
            this.ForeColor = Color.FromArgb(24, 35, 58);
            this.Text = "Business Suite | CRM directory";
            this.ClientSize = new Size(1160, 630);
            this.MinimumSize = new Size(1080, 455);
            this.StartPosition = FormStartPosition.CenterParent;
            this.AcceptButton = this.searchButton;
            this.Name = "CrmDirectoryForm";
            ((System.ComponentModel.ISupportInitialize)this.grid.MasterTemplate).EndInit();
            ((System.ComponentModel.ISupportInitialize)this.grid).EndInit();
            this.ResumeLayout(false);
            this.PerformLayout();
        }

        private Label titleLabel;
        private Button newButton;
        private Button editButton;
        private Button archiveButton;
        private Button restoreButton;
        private Button viewButton;
        private Button exportButton;
        private SaveFileDialog exportDialog;
        private ContextMenuStrip gridMenu;
        private ToolStripMenuItem copyRowMenuItem;
        private CueTextBox searchBox;
        private ComboBox roleFilter;
        private CheckBox archivedCheck;
        private Button searchButton;
        private Button refreshButton;
        private RadGridView grid;
        private GridViewTextBoxColumn nameColumn;
        private GridViewTextBoxColumn classificationColumn;
        private GridViewTextBoxColumn contextColumn;
        private GridViewTextBoxColumn emailColumn;
        private GridViewTextBoxColumn phoneColumn;
        private GridViewTextBoxColumn cityColumn;
        private GridViewTextBoxColumn countryColumn;
        private GridViewTextBoxColumn statusColumn;
        private Label statusLabel;
        private Button previousButton;
        private Button nextButton;
    }
}
