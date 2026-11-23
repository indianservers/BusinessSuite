#nullable disable
using System;
using System.Drawing;
using System.Windows.Forms;
using Telerik.WinControls.UI;

namespace Business_Suite
{
    partial class LeadsForm
    {
        private void InitializeComponent()
        {
            this.ownerBox = new ComboBox();
            this.heading = new Label();
            this.newButton = new Button();
            this.editButton = new Button();
            this.nurtureConsentButton = new Button();
            this.meetingMetricsButton = new Button();
            this.meetingOutcomesButton = new Button();
            this.leadTasksButton = new Button();
            this.leadHistoryButton = new Button();
            this.archiveButton = new Button();
            this.restoreButton = new Button();
            this.convertButton = new Button();
            this.searchBox = new CueTextBox();
            this.stageBox = new ComboBox();
            this.sourceBox = new CueTextBox();
            this.ratingBox = new ComboBox();
            this.archivedBox = new CheckBox();
            this.searchButton = new Button();
            this.refreshButton = new Button();
            this.exportFilteredButton = new Button();
            this.exportSelectedButton = new Button();
            this.exportDialog = new SaveFileDialog();
            this.grid = new RadGridView();
            this.leadColumn0 = new GridViewTextBoxColumn();
            this.leadColumn1 = new GridViewTextBoxColumn();
            this.leadColumn2 = new GridViewTextBoxColumn();
            this.leadColumn3 = new GridViewTextBoxColumn();
            this.leadColumn4 = new GridViewTextBoxColumn();
            this.leadColumn5 = new GridViewTextBoxColumn();
            this.leadColumn6 = new GridViewTextBoxColumn();
            this.leadColumn7 = new GridViewTextBoxColumn();
            this.leadColumn8 = new GridViewTextBoxColumn();
            this.statusLabel = new Label();
            this.previousButton = new Button();
            this.nextButton = new Button();
            ((System.ComponentModel.ISupportInitialize)this.grid).BeginInit();
            this.SuspendLayout();
            this.ownerBox.Location = new Point(657, 84);
            this.ownerBox.Size = new Size(126, 30);
            this.ownerBox.Name = "ownerBox";
            this.ownerBox.AccessibleName = "Lead owner filter";
            this.ownerBox.DropDownStyle = ComboBoxStyle.DropDownList;
            this.ownerBox.SelectedIndexChanged += this.FilterChanged;
            this.Controls.Add(this.ownerBox);
            // heading
            this.heading.Location = new Point(24, 19);
            this.heading.Size = new Size(300, 48);
            this.heading.Name = "heading";
            this.heading.Text = "CRM Leads";
            this.heading.Font = new Font("Segoe UI Semibold", 26F);
            // newButton
            this.newButton.Location = new Point(543, 26);
            this.newButton.Size = new Size(102, 37);
            this.newButton.Name = "newButton";
            this.newButton.Text = "New lead";
            this.newButton.Enabled = false;
            this.newButton.Click += this.NewClicked;
            // editButton
            this.editButton.Location = new Point(651, 26);
            this.editButton.Size = new Size(102, 37);
            this.editButton.Name = "editButton";
            this.editButton.Text = "Edit";
            this.editButton.Enabled = false;
            this.editButton.Click += this.EditClicked;
            this.nurtureConsentButton.Name = "nurtureConsentButton";
            this.nurtureConsentButton.Location = new Point(419, 26);
            this.nurtureConsentButton.Size = new Size(116, 37);
            this.nurtureConsentButton.Text = "Lead nurture";
            this.nurtureConsentButton.Enabled = false;
            this.nurtureConsentButton.Click += this.NurtureConsentClicked;
            this.meetingMetricsButton.Name = "meetingMetricsButton";
            this.meetingMetricsButton.Location = new Point(24, 553);
            this.meetingMetricsButton.Size = new Size(160, 38);
            this.meetingMetricsButton.Anchor = AnchorStyles.Left | AnchorStyles.Bottom;
            this.meetingMetricsButton.Text = "Consultations and demos";
            this.meetingMetricsButton.Enabled = false;
            this.meetingMetricsButton.Click += this.MeetingMetricsClicked;
            this.meetingOutcomesButton.Name = "meetingOutcomesButton";
            this.meetingOutcomesButton.Location = new Point(195, 553);
            this.meetingOutcomesButton.Size = new Size(125, 38);
            this.meetingOutcomesButton.Anchor = AnchorStyles.Left | AnchorStyles.Bottom;
            this.meetingOutcomesButton.Text = "Lead meetings";
            this.meetingOutcomesButton.Enabled = false;
            this.meetingOutcomesButton.Click += this.MeetingOutcomesClicked;
            this.leadTasksButton.Name = "leadTasksButton";
            this.leadTasksButton.Location = new Point(331, 553);
            this.leadTasksButton.Size = new Size(99, 38);
            this.leadTasksButton.Anchor = AnchorStyles.Left | AnchorStyles.Bottom;
            this.leadTasksButton.Text = "Lead tasks";
            this.leadTasksButton.Enabled = false;
            this.leadTasksButton.Click += this.LeadTasksClicked;
            this.leadHistoryButton.Name = "leadHistoryButton";
            this.leadHistoryButton.Location = new Point(332, 26);
            this.leadHistoryButton.Size = new Size(78, 37);
            this.leadHistoryButton.Text = "Preview";
            this.leadHistoryButton.Enabled = false;
            this.leadHistoryButton.Click += this.LeadHistoryClicked;
            // archiveButton
            this.archiveButton.Location = new Point(759, 26);
            this.archiveButton.Size = new Size(102, 37);
            this.archiveButton.Name = "archiveButton";
            this.archiveButton.Text = "Archive";
            this.archiveButton.Enabled = false;
            this.archiveButton.Click += this.ArchiveClicked;
            // restoreButton
            this.restoreButton.Location = new Point(867, 26);
            this.restoreButton.Size = new Size(102, 37);
            this.restoreButton.Name = "restoreButton";
            this.restoreButton.Text = "Restore";
            this.restoreButton.Enabled = false;
            this.restoreButton.Click += this.RestoreClicked;
            // convertButton
            this.convertButton.Location = new Point(975, 26);
            this.convertButton.Size = new Size(102, 37);
            this.convertButton.Name = "convertButton";
            this.convertButton.Text = "Convert lead";
            this.convertButton.Enabled = false;
            this.convertButton.Click += this.ConvertClicked;
            // searchBox
            this.searchBox.Location = new Point(24, 84);
            this.searchBox.Size = new Size(218, 30);
            this.searchBox.Name = "searchBox";
            this.searchBox.PlaceholderText = "Search name, company, email or phone";
            this.searchBox.AccessibleName = "Search leads";
            this.searchBox.MaxLength = 180;
            // stageBox
            this.stageBox.Location = new Point(252, 84);
            this.stageBox.Size = new Size(130, 30);
            this.stageBox.Name = "stageBox";
            this.stageBox.DropDownStyle = ComboBoxStyle.DropDownList;
            this.stageBox.SelectedIndexChanged += this.FilterChanged;
            // sourceBox
            this.sourceBox.Location = new Point(395, 84);
            this.sourceBox.Size = new Size(144, 30);
            this.sourceBox.Name = "sourceBox";
            this.sourceBox.PlaceholderText = "Lead source";
            this.sourceBox.AccessibleName = "Lead source filter";
            this.sourceBox.MaxLength = 80;
            // ratingBox
            this.ratingBox.Location = new Point(548, 84);
            this.ratingBox.Size = new Size(104, 30);
            this.ratingBox.Name = "ratingBox";
            this.ratingBox.DropDownStyle = ComboBoxStyle.DropDownList;
            this.ratingBox.SelectedIndexChanged += this.FilterChanged;
            // archivedBox
            this.archivedBox.Location = new Point(790, 83);
            this.archivedBox.Size = new Size(73, 30);
            this.archivedBox.Name = "archivedBox";
            this.archivedBox.Text = "Archived";
            this.archivedBox.CheckedChanged += this.FilterChanged;
            // searchButton
            this.searchButton.Location = new Point(864, 80);
            this.searchButton.Size = new Size(106, 34);
            this.searchButton.Name = "searchButton";
            this.searchButton.Text = "Apply filters";
            this.searchButton.Enabled = true;
            this.searchButton.Click += this.FilterChanged;
            // refreshButton
            this.refreshButton.Location = new Point(975, 80);
            this.refreshButton.Size = new Size(102, 34);
            this.refreshButton.Name = "refreshButton";
            this.refreshButton.Text = "Refresh";
            this.refreshButton.Enabled = true;
            this.refreshButton.Click += this.RefreshClicked;
            // grid
            this.grid.Location = new Point(24, 131);
            this.grid.Size = new Size(1053, 415);
            this.grid.Name = "grid";
            this.grid.Anchor = AnchorStyles.Top | AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
            this.grid.MasterTemplate.AllowAddNewRow = false;
            this.grid.MasterTemplate.AllowDeleteRow = false;
            this.grid.MasterTemplate.AutoGenerateColumns = false;
            this.grid.MasterTemplate.MultiSelect = true;
            this.grid.MasterTemplate.AutoSizeColumnsMode = GridViewAutoSizeColumnsMode.Fill;
            this.grid.ReadOnly = true;
            this.grid.ShowGroupPanel = false;
            this.grid.SelectionChanged += this.SelectionChanged;
            // leadColumn0
            this.leadColumn0.Name = "full_name";
            this.leadColumn0.FieldName = "full_name";
            this.leadColumn0.HeaderText = "Lead";
            this.leadColumn0.Width = 185;
            // leadColumn1
            this.leadColumn1.Name = "company_name";
            this.leadColumn1.FieldName = "company_name";
            this.leadColumn1.HeaderText = "Company";
            this.leadColumn1.Width = 145;
            // leadColumn2
            this.leadColumn2.Name = "status";
            this.leadColumn2.FieldName = "status";
            this.leadColumn2.HeaderText = "Stage";
            this.leadColumn2.Width = 85;
            // leadColumn3
            this.leadColumn3.Name = "rating";
            this.leadColumn3.FieldName = "rating";
            this.leadColumn3.HeaderText = "Rating";
            this.leadColumn3.Width = 68;
            // leadColumn4
            this.leadColumn4.Name = "source";
            this.leadColumn4.FieldName = "source";
            this.leadColumn4.HeaderText = "Source";
            this.leadColumn4.Width = 95;
            // leadColumn5
            this.leadColumn5.Name = "email";
            this.leadColumn5.FieldName = "email";
            this.leadColumn5.HeaderText = "Email";
            this.leadColumn5.Width = 150;
            // leadColumn6
            this.leadColumn6.Name = "phone_display";
            this.leadColumn6.FieldName = "phone_display";
            this.leadColumn6.HeaderText = "Phone";
            this.leadColumn6.Width = 115;
            // leadColumn7
            this.leadColumn7.Name = "estimated_value";
            this.leadColumn7.FieldName = "estimated_value";
            this.leadColumn7.HeaderText = "Estimated value";
            this.leadColumn7.Width = 98;
            // leadColumn8
            this.leadColumn8.Name = "next_follow_up_at";
            this.leadColumn8.FieldName = "next_follow_up_at";
            this.leadColumn8.HeaderText = "Follow-up";
            this.leadColumn8.Width = 140;
            // statusLabel
            this.statusLabel.Location = new Point(441, 553);
            this.statusLabel.Size = new Size(131, 38);
            this.statusLabel.Name = "statusLabel";
            this.statusLabel.Anchor = AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
            this.statusLabel.TextAlign = ContentAlignment.MiddleLeft;
            // exportFilteredButton
            this.exportFilteredButton.Name = "exportFilteredButton";
            this.exportFilteredButton.Location = new Point(580, 553);
            this.exportFilteredButton.Size = new Size(140, 38);
            this.exportFilteredButton.Anchor = AnchorStyles.Bottom | AnchorStyles.Right;
            this.exportFilteredButton.Enabled = false;
            this.exportFilteredButton.Text = "Export filtered";
            this.exportFilteredButton.Click += this.ExportFilteredClicked;
            // exportSelectedButton
            this.exportSelectedButton.Name = "exportSelectedButton";
            this.exportSelectedButton.Location = new Point(730, 553);
            this.exportSelectedButton.Size = new Size(140, 38);
            this.exportSelectedButton.Anchor = AnchorStyles.Bottom | AnchorStyles.Right;
            this.exportSelectedButton.Enabled = false;
            this.exportSelectedButton.Text = "Export selected";
            this.exportSelectedButton.Click += this.ExportSelectedClicked;
            // exportDialog
            this.exportDialog.AddExtension = true;
            this.exportDialog.DefaultExt = "xlsx";
            this.exportDialog.Filter = "Excel workbook (*.xlsx)|*.xlsx";
            this.exportDialog.Title = "Save lead workbook";
            this.exportDialog.RestoreDirectory = true;
            // previousButton
            this.previousButton.Location = new Point(880, 553);
            this.previousButton.Size = new Size(92, 38);
            this.previousButton.Name = "previousButton";
            this.previousButton.Text = "Previous";
            this.previousButton.Enabled = false;
            this.previousButton.Anchor = AnchorStyles.Bottom | AnchorStyles.Right;
            this.previousButton.Click += this.PreviousClicked;
            // nextButton
            this.nextButton.Location = new Point(982, 553);
            this.nextButton.Size = new Size(95, 38);
            this.nextButton.Name = "nextButton";
            this.nextButton.Text = "Next";
            this.nextButton.Enabled = false;
            this.nextButton.Anchor = AnchorStyles.Bottom | AnchorStyles.Right;
            this.nextButton.Click += this.NextClicked;
            this.grid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] { this.leadColumn0, this.leadColumn1, this.leadColumn2, this.leadColumn3, this.leadColumn4, this.leadColumn5, this.leadColumn6, this.leadColumn7, this.leadColumn8 });
            this.Shown += this.LeadsShown;
            this.FormClosed += this.LeadsClosed;
            this.Controls.Add(this.heading);
            this.Controls.Add(this.newButton);
            this.Controls.Add(this.editButton);
            this.Controls.Add(this.nurtureConsentButton);
            this.Controls.Add(this.meetingMetricsButton);
            this.Controls.Add(this.meetingOutcomesButton);
            this.Controls.Add(this.leadTasksButton);
            this.Controls.Add(this.leadHistoryButton);
            this.Controls.Add(this.archiveButton);
            this.Controls.Add(this.restoreButton);
            this.Controls.Add(this.convertButton);
            this.Controls.Add(this.searchBox);
            this.Controls.Add(this.stageBox);
            this.Controls.Add(this.sourceBox);
            this.Controls.Add(this.ratingBox);
            this.Controls.Add(this.archivedBox);
            this.Controls.Add(this.searchButton);
            this.Controls.Add(this.refreshButton);
            this.Controls.Add(this.grid);
            this.Controls.Add(this.statusLabel);
            this.Controls.Add(this.exportFilteredButton);
            this.Controls.Add(this.exportSelectedButton);
            this.Controls.Add(this.previousButton);
            this.Controls.Add(this.nextButton);
            this.AutoScaleDimensions = new SizeF(96F, 96F);
            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.Font = new Font("Segoe UI", 10F);
            this.BackColor = Color.FromArgb(243, 246, 251);
            this.ForeColor = Color.FromArgb(24, 35, 58);
            this.Text = "Business Suite | CRM Leads";
            this.ClientSize = new Size(1100, 610);
            this.MinimumSize = new Size(1118, 460);
            this.StartPosition = FormStartPosition.CenterParent;
            this.AcceptButton = this.searchButton;
            this.Name = "LeadsForm";
            ((System.ComponentModel.ISupportInitialize)this.grid).EndInit();
            this.ResumeLayout(false);
            this.PerformLayout();
        }

        private ComboBox ownerBox;
        private Label heading;
        private Button newButton;
        private Button editButton;
        private Button nurtureConsentButton;
        private Button meetingMetricsButton;
        private Button meetingOutcomesButton;
        private Button leadTasksButton;
        private Button leadHistoryButton;
        private Button archiveButton;
        private Button restoreButton;
        private Button convertButton;
        private CueTextBox searchBox;
        private ComboBox stageBox;
        private CueTextBox sourceBox;
        private ComboBox ratingBox;
        private CheckBox archivedBox;
        private Button searchButton;
        private Button refreshButton;
        private Button exportFilteredButton;
        private Button exportSelectedButton;
        private SaveFileDialog exportDialog;
        private RadGridView grid;
        private GridViewTextBoxColumn leadColumn0;
        private GridViewTextBoxColumn leadColumn1;
        private GridViewTextBoxColumn leadColumn2;
        private GridViewTextBoxColumn leadColumn3;
        private GridViewTextBoxColumn leadColumn4;
        private GridViewTextBoxColumn leadColumn5;
        private GridViewTextBoxColumn leadColumn6;
        private GridViewTextBoxColumn leadColumn7;
        private GridViewTextBoxColumn leadColumn8;
        private Label statusLabel;
        private Button previousButton;
        private Button nextButton;
    }
}
