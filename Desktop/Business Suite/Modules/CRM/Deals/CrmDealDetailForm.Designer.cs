#nullable disable
using Telerik.WinControls.UI;

namespace Business_Suite;

partial class CrmDealDetailForm
{
    private void InitializeComponent()
    {
        this.heading = new Label();
        this.detailTabs = new TabControl();
        this.overviewTab = new TabPage();
        this.peopleTab = new TabPage();
        this.historyTab = new TabPage();
        this.notesTab = new TabPage();
        this.notesGrid = new RadGridView();
        this.noteAuthorColumn = new GridViewTextBoxColumn();
        this.noteCreatedColumn = new GridViewDateTimeColumn();
        this.notePinnedColumn = new GridViewCheckBoxColumn();
        this.noteBodyBox = new TextBox();
        this.notesStatus = new Label();
        this.addNoteButton = new Button();
        this.editNoteButton = new Button();
        this.pinNoteButton = new Button();
        this.archiveNoteButton = new Button();
        this.detailsBox = new TextBox();
        this.peopleGrid = new RadGridView();
        this.contactColumn = new GridViewTextBoxColumn();
        this.roleColumn = new GridViewTextBoxColumn();
        this.influence_levelColumn = new GridViewTextBoxColumn();
        this.is_primaryColumn = new GridViewCheckBoxColumn();
        this.peopleStatus = new Label();
        this.editStakeholdersButton = new Button();
        this.collaboratorsButton = new Button();
        this.historyGrid = new RadGridView();
        this.occurredColumn = new GridViewDateTimeColumn();
        this.titleColumn = new GridViewTextBoxColumn();
        this.descriptionColumn = new GridViewTextBoxColumn();
        this.historyStatus = new Label();
        this.tasksButton = new Button();
        this.callsButton = new Button();
        this.meetingsButton = new Button();
        this.closeButton = new Button();
        this.editButton = new Button();
        this.closeDealButton = new Button();
        ((System.ComponentModel.ISupportInitialize)this.peopleGrid).BeginInit();
        ((System.ComponentModel.ISupportInitialize)this.peopleGrid.MasterTemplate).BeginInit();
        ((System.ComponentModel.ISupportInitialize)this.historyGrid).BeginInit();
        ((System.ComponentModel.ISupportInitialize)this.historyGrid.MasterTemplate).BeginInit();
        ((System.ComponentModel.ISupportInitialize)this.notesGrid).BeginInit();
        ((System.ComponentModel.ISupportInitialize)this.notesGrid.MasterTemplate).BeginInit();
        this.SuspendLayout();

        this.heading.Name = "heading";
        this.heading.Location = new Point(22, 15);
        this.heading.Size = new Size(749, 48);
        this.heading.Text = "Deal details";
        this.heading.Font = new Font("Segoe UI Semibold", 23F);
        this.heading.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
        this.Controls.Add(this.heading);

        this.detailTabs.Name = "detailTabs";
        this.detailTabs.Location = new Point(22, 77);
        this.detailTabs.Size = new Size(752, 417);
        this.detailTabs.Anchor = AnchorStyles.Top | AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
        this.Controls.Add(this.detailTabs);

        this.overviewTab.Name = "overviewTab";
        this.overviewTab.Text = "Overview";

        this.detailTabs.TabPages.Add(this.overviewTab);
        this.peopleTab.Name = "peopleTab";
        this.peopleTab.Text = "Contacts";

        this.detailTabs.TabPages.Add(this.peopleTab);
        this.historyTab.Name = "historyTab";
        this.historyTab.Text = "History";

        this.detailTabs.TabPages.Add(this.historyTab);
        this.notesTab.Name = "notesTab";
        this.notesTab.Text = "Notes";
        this.detailTabs.TabPages.Add(this.notesTab);

        this.notesGrid.Name = "notesGrid";
        this.notesGrid.Location = new Point(13, 13);
        this.notesGrid.Size = new Size(713, 197);
        this.notesGrid.Anchor = AnchorStyles.Top | AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
        this.notesGrid.MasterTemplate.AutoGenerateColumns = false;
        this.notesGrid.MasterTemplate.AutoSizeColumnsMode = GridViewAutoSizeColumnsMode.Fill;
        this.notesGrid.MasterTemplate.AllowAddNewRow = false;
        this.notesGrid.MasterTemplate.AllowDeleteRow = false;
        this.notesGrid.ReadOnly = true;
        this.notesGrid.ShowGroupPanel = false;
        this.notesGrid.SelectionChanged += this.NoteSelectionChanged;
        this.noteCreatedColumn.Name = "noteCreatedColumn";
        this.noteCreatedColumn.HeaderText = "Created";
        this.noteCreatedColumn.FieldName = "created_at";
        this.noteAuthorColumn.Name = "noteAuthorColumn";
        this.noteAuthorColumn.HeaderText = "Author";
        this.noteAuthorColumn.FieldName = "author";
        this.notePinnedColumn.Name = "notePinnedColumn";
        this.notePinnedColumn.HeaderText = "Pinned";
        this.notePinnedColumn.FieldName = "is_pinned";
        this.notesGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] {
            this.noteCreatedColumn,this.noteAuthorColumn,this.notePinnedColumn
        });
        this.notesTab.Controls.Add(this.notesGrid);

        this.noteBodyBox.Name = "noteBodyBox";
        this.noteBodyBox.AccessibleName = "Selected note";
        this.noteBodyBox.Location = new Point(13, 221);
        this.noteBodyBox.Size = new Size(713, 116);
        this.noteBodyBox.Anchor = AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
        this.noteBodyBox.Multiline = true;
        this.noteBodyBox.ReadOnly = true;
        this.noteBodyBox.ScrollBars = ScrollBars.Vertical;
        this.notesTab.Controls.Add(this.noteBodyBox);
        this.notesStatus.Name = "notesStatus";
        this.notesStatus.Location = new Point(14, 348);
        this.notesStatus.Size = new Size(365, 29);
        this.notesStatus.Anchor = AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
        this.notesTab.Controls.Add(this.notesStatus);
        this.addNoteButton.Name = "addNoteButton";
        this.addNoteButton.Text = "Add note";
        this.addNoteButton.Location = new Point(386, 343);
        this.addNoteButton.Size = new Size(96, 30);
        this.addNoteButton.Anchor = AnchorStyles.Bottom | AnchorStyles.Right;
        this.addNoteButton.Enabled = false;
        this.addNoteButton.Click += this.AddNoteClicked;
        this.notesTab.Controls.Add(this.addNoteButton);
        this.editNoteButton.Name = "editNoteButton";
        this.editNoteButton.Text = "Edit";
        this.editNoteButton.Location = new Point(490, 343);
        this.editNoteButton.Size = new Size(72, 30);
        this.editNoteButton.Anchor = AnchorStyles.Bottom | AnchorStyles.Right;
        this.editNoteButton.Enabled = false;
        this.editNoteButton.Click += this.EditNoteClicked;
        this.notesTab.Controls.Add(this.editNoteButton);
        this.pinNoteButton.Name = "pinNoteButton";
        this.pinNoteButton.Text = "Pin";
        this.pinNoteButton.Location = new Point(570, 343);
        this.pinNoteButton.Size = new Size(66, 30);
        this.pinNoteButton.Anchor = AnchorStyles.Bottom | AnchorStyles.Right;
        this.pinNoteButton.Enabled = false;
        this.pinNoteButton.Click += this.PinNoteClicked;
        this.notesTab.Controls.Add(this.pinNoteButton);
        this.archiveNoteButton.Name = "archiveNoteButton";
        this.archiveNoteButton.Text = "Archive";
        this.archiveNoteButton.Location = new Point(644, 343);
        this.archiveNoteButton.Size = new Size(81, 30);
        this.archiveNoteButton.Anchor = AnchorStyles.Bottom | AnchorStyles.Right;
        this.archiveNoteButton.Enabled = false;
        this.archiveNoteButton.Click += this.ArchiveNoteClicked;
        this.notesTab.Controls.Add(this.archiveNoteButton);
        this.detailsBox.Name = "detailsBox";
        this.detailsBox.Location = new Point(13, 13);
        this.detailsBox.Size = new Size(713, 358);
        this.detailsBox.Multiline = true;
        this.detailsBox.ReadOnly = true;
        this.detailsBox.WordWrap = true;
        this.detailsBox.ScrollBars = ScrollBars.Vertical;
        this.detailsBox.Anchor = AnchorStyles.Top | AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
        this.overviewTab.Controls.Add(this.detailsBox);

        this.peopleGrid.Name = "peopleGrid";
        this.peopleGrid.Location = new Point(13, 13);
        this.peopleGrid.Size = new Size(713, 326);
        this.peopleGrid.MasterTemplate.AutoGenerateColumns = false;
        this.peopleGrid.MasterTemplate.AutoSizeColumnsMode = GridViewAutoSizeColumnsMode.Fill;
        this.peopleGrid.MasterTemplate.AllowAddNewRow = false;
        this.peopleGrid.MasterTemplate.AllowDeleteRow = false;
        this.peopleGrid.ReadOnly = true;
        this.peopleGrid.ShowGroupPanel = false;
        this.peopleGrid.Anchor = AnchorStyles.Top | AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
        this.peopleTab.Controls.Add(this.peopleGrid);

        this.contactColumn.Name = "contactColumn";
        this.contactColumn.FieldName = "contact";
        this.contactColumn.HeaderText = "Contact";
        this.contactColumn.Width = 200;
        this.roleColumn.Name = "roleColumn";
        this.roleColumn.FieldName = "role";
        this.roleColumn.HeaderText = "Role";
        this.roleColumn.Width = 130;
        this.influence_levelColumn.Name = "influence_levelColumn";
        this.influence_levelColumn.FieldName = "influence_level";
        this.influence_levelColumn.HeaderText = "Influence level";
        this.influence_levelColumn.Width = 134;
        this.is_primaryColumn.Name = "is_primaryColumn";
        this.is_primaryColumn.FieldName = "is_primary";
        this.is_primaryColumn.HeaderText = "Primary contact";
        this.is_primaryColumn.Width = 110;
        this.peopleGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] { this.contactColumn, this.roleColumn, this.influence_levelColumn, this.is_primaryColumn });

        this.peopleStatus.Name = "peopleStatus";
        this.peopleStatus.Location = new Point(14, 348);
        this.peopleStatus.Size = new Size(340, 22);
        this.peopleStatus.Anchor = AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
        this.peopleTab.Controls.Add(this.peopleStatus);

        this.collaboratorsButton.Name = "collaboratorsButton";
        this.collaboratorsButton.Location = new Point(375, 343);
        this.collaboratorsButton.Size = new Size(175, 30);
        this.collaboratorsButton.Anchor = AnchorStyles.Bottom | AnchorStyles.Right;
        this.collaboratorsButton.Text = "Collaborators";
        this.collaboratorsButton.Click += this.CollaboratorsClicked;
        this.peopleTab.Controls.Add(this.collaboratorsButton);

        this.editStakeholdersButton.Name = "editStakeholdersButton";
        this.editStakeholdersButton.Location = new Point(558, 343);
        this.editStakeholdersButton.Size = new Size(167, 30);
        this.editStakeholdersButton.Anchor = AnchorStyles.Bottom | AnchorStyles.Right;
        this.editStakeholdersButton.Text = "Edit stakeholders";
        this.editStakeholdersButton.Click += this.EditStakeholdersClicked;
        this.peopleTab.Controls.Add(this.editStakeholdersButton);

        this.historyGrid.Name = "historyGrid";
        this.historyGrid.Location = new Point(13, 13);
        this.historyGrid.Size = new Size(713, 326);
        this.historyGrid.MasterTemplate.AutoGenerateColumns = false;
        this.historyGrid.MasterTemplate.AutoSizeColumnsMode = GridViewAutoSizeColumnsMode.Fill;
        this.historyGrid.MasterTemplate.AllowAddNewRow = false;
        this.historyGrid.MasterTemplate.AllowDeleteRow = false;
        this.historyGrid.ReadOnly = true;
        this.historyGrid.ShowGroupPanel = false;
        this.historyGrid.Anchor = AnchorStyles.Top | AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
        this.historyTab.Controls.Add(this.historyGrid);

        this.occurredColumn.Name = "occurredColumn";
        this.occurredColumn.FieldName = "occurred";
        this.occurredColumn.HeaderText = "When";
        this.occurredColumn.Width = 135;
        this.occurredColumn.FormatString = "{0:dd MMM yyyy HH:mm}";
        this.titleColumn.Name = "titleColumn";
        this.titleColumn.FieldName = "title";
        this.titleColumn.HeaderText = "Action";
        this.titleColumn.Width = 160;
        this.descriptionColumn.Name = "descriptionColumn";
        this.descriptionColumn.FieldName = "description";
        this.descriptionColumn.HeaderText = "Description";
        this.descriptionColumn.Width = 277;
        this.historyGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] { this.occurredColumn, this.titleColumn, this.descriptionColumn });

        this.historyStatus.Name = "historyStatus";
        this.historyStatus.Location = new Point(14, 348);
        this.historyStatus.Size = new Size(227, 31);
        this.historyStatus.Anchor = AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
        this.historyTab.Controls.Add(this.historyStatus);

        this.tasksButton.Name = "tasksButton";
        this.tasksButton.Text = "Deal tasks";
        this.tasksButton.Location = new Point(558, 343);
        this.tasksButton.Size = new Size(167, 30);
        this.tasksButton.Anchor = AnchorStyles.Bottom | AnchorStyles.Right;
        this.tasksButton.Click += this.TasksClicked;
        this.historyTab.Controls.Add(this.tasksButton);

        this.callsButton.Name = "callsButton";
        this.callsButton.Text = "Deal calls";
        this.callsButton.Location = new Point(406, 343);
        this.callsButton.Size = new Size(143, 30);
        this.callsButton.Anchor = AnchorStyles.Bottom | AnchorStyles.Right;
        this.callsButton.Click += this.CallsClicked;
        this.historyTab.Controls.Add(this.callsButton);

        this.meetingsButton.Name = "meetingsButton";
        this.meetingsButton.Text = "Deal meetings";
        this.meetingsButton.Location = new Point(250, 343);
        this.meetingsButton.Size = new Size(147, 30);
        this.meetingsButton.Anchor = AnchorStyles.Bottom | AnchorStyles.Right;
        this.meetingsButton.Click += this.MeetingsClicked;
        this.historyTab.Controls.Add(this.meetingsButton);

        this.closeDealButton.Name = "closeDealButton";
        this.closeDealButton.Location = new Point(441, 513);
        this.closeDealButton.Size = new Size(112, 35);
        this.closeDealButton.Text = "Close deal";
        this.closeDealButton.Visible = false;
        this.closeDealButton.Anchor = AnchorStyles.Bottom | AnchorStyles.Right;
        this.closeDealButton.Click += this.CloseDealClicked;
        this.Controls.Add(this.closeDealButton);

        this.editButton.Name = "editButton";
        this.editButton.Location = new Point(565, 513);
        this.editButton.Size = new Size(98, 35);
        this.editButton.Text = "Edit deal";
        this.editButton.Visible = false;
        this.editButton.Anchor = AnchorStyles.Bottom | AnchorStyles.Right;
        this.editButton.Click += this.EditClicked;
        this.Controls.Add(this.editButton);

        this.closeButton.Name = "closeButton";
        this.closeButton.Location = new Point(676, 513);
        this.closeButton.Size = new Size(98, 35);
        this.closeButton.Text = "Close";
        this.closeButton.DialogResult = DialogResult.Cancel;
        this.closeButton.Anchor = AnchorStyles.Bottom | AnchorStyles.Right;
        this.Controls.Add(this.closeButton);

        this.Text = "Business Suite | Deal details";
        this.Name = "CrmDealDetailForm";
        this.ClientSize = new Size(800, 568);
        this.StartPosition = FormStartPosition.CenterParent;
        this.Font = new Font("Segoe UI", 10F);
        this.AutoScaleDimensions = new SizeF(96F, 96F);
        this.AutoScaleMode = AutoScaleMode.Dpi;
        this.BackColor = Color.FromArgb(243, 246, 251);
        this.ForeColor = Color.FromArgb(24, 35, 58);
        this.MinimumSize = new Size(664, 470);
        this.CancelButton = this.closeButton;
        ((System.ComponentModel.ISupportInitialize)this.peopleGrid.MasterTemplate).EndInit();
        ((System.ComponentModel.ISupportInitialize)this.notesGrid.MasterTemplate).EndInit();
        ((System.ComponentModel.ISupportInitialize)this.notesGrid).EndInit();
        ((System.ComponentModel.ISupportInitialize)this.peopleGrid).EndInit();
        ((System.ComponentModel.ISupportInitialize)this.historyGrid.MasterTemplate).EndInit();
        ((System.ComponentModel.ISupportInitialize)this.historyGrid).EndInit();
        this.ResumeLayout(false);
        this.PerformLayout();
    }

    private Label heading;
    private TabControl detailTabs;
    private TabPage overviewTab;
    private TabPage peopleTab;
    private TabPage historyTab;
    private TextBox detailsBox;
    private RadGridView peopleGrid;
    private TabPage notesTab;
    private RadGridView notesGrid;
    private GridViewDateTimeColumn noteCreatedColumn;
    private GridViewTextBoxColumn noteAuthorColumn;
    private GridViewCheckBoxColumn notePinnedColumn;
    private TextBox noteBodyBox;
    private Label notesStatus;
    private Button addNoteButton;
    private Button editNoteButton;
    private Button pinNoteButton;
    private Button archiveNoteButton;
    private GridViewTextBoxColumn contactColumn;
    private GridViewTextBoxColumn roleColumn;
    private GridViewTextBoxColumn influence_levelColumn;
    private GridViewCheckBoxColumn is_primaryColumn;
    private Label peopleStatus;
    private Button editStakeholdersButton;
    private Button collaboratorsButton;
    private RadGridView historyGrid;
    private GridViewDateTimeColumn occurredColumn;
    private GridViewTextBoxColumn titleColumn;
    private GridViewTextBoxColumn descriptionColumn;
    private Label historyStatus;
    private Button tasksButton;
    private Button callsButton;
    private Button meetingsButton;
    private Button closeButton;
    private Button editButton;
    private Button closeDealButton;
}
