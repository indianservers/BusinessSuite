#nullable disable
using System.Drawing;
using System.Windows.Forms;
using Telerik.WinControls.UI;

namespace Business_Suite
{
    partial class PmsWorkspacesForm
    {
        private void InitializeComponent()
        {
            this.toolbar = new Panel();
            this.newWorkspaceName = new RadTextBox();
            this.createButton = new RadButton();
            this.openButton = new RadButton();
            this.refreshButton = new RadButton();
            this.membersButton = new RadButton();
            this.myInvitesButton = new RadButton();
            this.recoveryButton = new RadButton();
            this.workspaceGrid = new RadGridView();
            this.statusLabel = new Label();
            this.nameColumn = new GridViewTextBoxColumn();
            this.roleColumn = new GridViewTextBoxColumn();
            this.membersColumn = new GridViewTextBoxColumn();
            this.projectsColumn = new GridViewTextBoxColumn();
            this.tasksColumn = new GridViewTextBoxColumn();
            this.completedColumn = new GridViewTextBoxColumn();
            this.createdColumn = new GridViewTextBoxColumn();
            ((System.ComponentModel.ISupportInitialize)this.workspaceGrid).BeginInit();
            ((System.ComponentModel.ISupportInitialize)this.workspaceGrid.MasterTemplate).BeginInit();
            this.toolbar.SuspendLayout();
            this.SuspendLayout();

            this.newWorkspaceName.Name = "newWorkspaceName";
            this.newWorkspaceName.NullText = "New workspace name";
            this.newWorkspaceName.MaxLength = 180;
            this.newWorkspaceName.Location = new Point(10, 12);
            this.newWorkspaceName.Size = new Size(230, 25);
            this.newWorkspaceName.TextChanged += this.NewWorkspaceNameChanged;

            this.createButton.Name = "createButton";
            this.createButton.Text = "Create workspace";
            this.createButton.Location = new Point(250, 10);
            this.createButton.Size = new Size(125, 28);
            this.createButton.Click += this.CreateWorkspaceClicked;

            this.openButton.Name = "openButton";
            this.openButton.Text = "Open projects";
            this.openButton.Location = new Point(390, 10);
            this.openButton.Size = new Size(112, 28);
            this.openButton.Click += this.OpenWorkspaceClicked;

            this.refreshButton.Name = "refreshButton";
            this.refreshButton.Text = "Refresh";
            this.refreshButton.Location = new Point(512, 10);
            this.refreshButton.Size = new Size(75, 28);
            this.refreshButton.Click += this.LoadWorkspacesClicked;

            this.membersButton.Name = "membersButton";
            this.membersButton.Text = "Members";
            this.membersButton.Location = new Point(598, 10);
            this.membersButton.Size = new Size(85, 28);
            this.membersButton.Enabled = false;
            this.membersButton.Click += this.OpenMembersClicked;

            this.myInvitesButton.Name = "myInvitesButton";
            this.myInvitesButton.Text = "My invitations";
            this.myInvitesButton.Location = new Point(694, 10);
            this.myInvitesButton.Size = new Size(111, 28);
            this.myInvitesButton.Click += this.OpenInvitationsClicked;

            this.recoveryButton.Name = "recoveryButton";
            this.recoveryButton.Text = "Workspace recovery";
            this.recoveryButton.Location = new Point(814, 10);
            this.recoveryButton.Size = new Size(140, 28);
            this.recoveryButton.Enabled = false;
            this.recoveryButton.Click += this.OpenRecoveryClicked;

            this.toolbar.Name = "toolbar";
            this.toolbar.Dock = DockStyle.Top;
            this.toolbar.Height = 50;
            this.toolbar.Controls.AddRange(new Control[] {
                this.newWorkspaceName, this.createButton, this.openButton, this.refreshButton,
                this.membersButton, this.myInvitesButton, this.recoveryButton });

            this.nameColumn.Name = "nameColumn";
            this.nameColumn.FieldName = "Name";
            this.nameColumn.HeaderText = "Workspace";
            this.nameColumn.Width = 240;

            this.roleColumn.Name = "roleColumn";
            this.roleColumn.FieldName = "Role";
            this.roleColumn.HeaderText = "Access role";
            this.roleColumn.Width = 110;

            this.membersColumn.Name = "membersColumn";
            this.membersColumn.FieldName = "MemberCount";
            this.membersColumn.HeaderText = "Members";
            this.membersColumn.Width = 85;

            this.projectsColumn.Name = "projectsColumn";
            this.projectsColumn.FieldName = "ProjectCount";
            this.projectsColumn.HeaderText = "Projects";
            this.projectsColumn.Width = 85;

            this.tasksColumn.Name = "tasksColumn";
            this.tasksColumn.FieldName = "TaskCount";
            this.tasksColumn.HeaderText = "Tasks";
            this.tasksColumn.Width = 85;

            this.completedColumn.Name = "completedColumn";
            this.completedColumn.FieldName = "CompletedTaskCount";
            this.completedColumn.HeaderText = "Completed tasks";
            this.completedColumn.Width = 135;

            this.createdColumn.Name = "createdColumn";
            this.createdColumn.FieldName = "CreatedAt";
            this.createdColumn.HeaderText = "Created";
            this.createdColumn.Width = 105;
            this.createdColumn.FormatString = "{0:d}";

            this.workspaceGrid.Name = "workspaceGrid";
            this.workspaceGrid.Dock = DockStyle.Fill;
            this.workspaceGrid.AutoGenerateColumns = false;
            this.workspaceGrid.ReadOnly = true;
            this.workspaceGrid.MasterTemplate.AllowAddNewRow = false;
            this.workspaceGrid.MasterTemplate.AllowDeleteRow = false;
            this.workspaceGrid.MasterTemplate.AllowEditRow = false;
            this.workspaceGrid.MasterTemplate.EnableFiltering = true;
            this.workspaceGrid.MasterTemplate.ShowFilteringRow = true;
            this.workspaceGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] {
                this.nameColumn, this.roleColumn, this.membersColumn, this.projectsColumn, this.tasksColumn, this.completedColumn, this.createdColumn });
            this.workspaceGrid.CurrentRowChanged += this.WorkspaceSelectionChanged;
            this.workspaceGrid.CellDoubleClick += this.WorkspaceDoubleClicked;

            this.statusLabel.Name = "statusLabel";
            this.statusLabel.Dock = DockStyle.Bottom;
            this.statusLabel.Padding = new Padding(10, 4, 10, 0);
            this.statusLabel.Height = 28;

            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.ClientSize = new Size(980, 600);
            this.MinimumSize = new Size(982, 400);
            this.Controls.Add(this.workspaceGrid);
            this.Controls.Add(this.statusLabel);
            this.Controls.Add(this.toolbar);
            this.Font = new Font("Segoe UI", 10F);
            this.Name = "PmsWorkspacesForm";
            this.StartPosition = FormStartPosition.CenterParent;
            this.Text = "Business Suite | Workspaces";
            this.Load += this.LoadWorkspacesClicked;
            ((System.ComponentModel.ISupportInitialize)this.workspaceGrid.MasterTemplate).EndInit();
            ((System.ComponentModel.ISupportInitialize)this.workspaceGrid).EndInit();
            this.toolbar.ResumeLayout(false);
            this.toolbar.PerformLayout();
            this.ResumeLayout(false);
        }

        private Panel toolbar;
        private RadTextBox newWorkspaceName;
        private RadButton createButton;
        private RadButton openButton;
        private RadButton refreshButton;
        private RadButton membersButton;
        private RadButton myInvitesButton;
        private RadButton recoveryButton;
        private RadGridView workspaceGrid;
        private GridViewTextBoxColumn nameColumn;
        private GridViewTextBoxColumn roleColumn;
        private GridViewTextBoxColumn membersColumn;
        private GridViewTextBoxColumn projectsColumn;
        private GridViewTextBoxColumn tasksColumn;
        private GridViewTextBoxColumn completedColumn;
        private GridViewTextBoxColumn createdColumn;
        private Label statusLabel;
    }
}
