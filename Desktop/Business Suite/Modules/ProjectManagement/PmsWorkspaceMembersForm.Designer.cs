#nullable disable
using System.Drawing;
using System.Windows.Forms;
using Telerik.WinControls.UI;

namespace Business_Suite
{
    partial class PmsWorkspaceMembersForm
    {
        private void InitializeComponent()
        {
            this.heading = new Label();
            this.memberGrid = new RadGridView();
            this.nameColumn = new GridViewTextBoxColumn();
            this.emailColumn = new GridViewTextBoxColumn();
            this.roleColumn = new GridViewTextBoxColumn();
            this.statusColumn = new GridViewTextBoxColumn();
            this.searchInput = new RadTextBox();
            this.searchButton = new RadButton();
            this.personInput = new RadDropDownList();
            this.roleInput = new RadDropDownList();
            this.addButton = new RadButton();
            this.changeRoleButton = new RadButton();
            this.removeButton = new RadButton();
            this.invitationsButton = new RadButton();
            this.statusLabel = new Label();
            this.closeButton = new RadButton();
            ((System.ComponentModel.ISupportInitialize)this.memberGrid).BeginInit();
            ((System.ComponentModel.ISupportInitialize)this.memberGrid.MasterTemplate).BeginInit();
            this.SuspendLayout();

            this.heading.Name = "heading";
            this.heading.Location = new Point(14, 12);
            this.heading.Size = new Size(466, 31);
            this.heading.Font = new Font("Segoe UI Semibold", 11F);

            this.nameColumn.Name = "nameColumn";
            this.nameColumn.FieldName = "name";
            this.nameColumn.HeaderText = "Name";
            this.nameColumn.Width = 190;

            this.emailColumn.Name = "emailColumn";
            this.emailColumn.FieldName = "email";
            this.emailColumn.HeaderText = "Email";
            this.emailColumn.Width = 270;

            this.roleColumn.Name = "roleColumn";
            this.roleColumn.FieldName = "role";
            this.roleColumn.HeaderText = "Workspace role";
            this.roleColumn.Width = 130;

            this.statusColumn.Name = "statusColumn";
            this.statusColumn.FieldName = "status";
            this.statusColumn.HeaderText = "Account status";
            this.statusColumn.Width = 135;

            this.memberGrid.Name = "memberGrid";
            this.memberGrid.Location = new Point(14, 50);
            this.memberGrid.Size = new Size(758, 320);
            this.memberGrid.AutoGenerateColumns = false;
            this.memberGrid.ReadOnly = true;
            this.memberGrid.MasterTemplate.AllowAddNewRow = false;
            this.memberGrid.MasterTemplate.AllowDeleteRow = false;
            this.memberGrid.MasterTemplate.AllowEditRow = false;
            this.memberGrid.CurrentRowChanged += this.MemberSelectionChanged;
            this.memberGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] {
                this.nameColumn, this.emailColumn, this.roleColumn, this.statusColumn });

            this.searchInput.Name = "searchInput";
            this.searchInput.NullText = "Find existing people";
            this.searchInput.Location = new Point(14, 388);
            this.searchInput.Size = new Size(194, 26);
            this.searchInput.MaxLength = 150;
            this.searchInput.KeyDown += this.SearchKeyDown;

            this.searchButton.Name = "searchButton";
            this.searchButton.Text = "Search";
            this.searchButton.Location = new Point(218, 386);
            this.searchButton.Size = new Size(77, 29);
            this.searchButton.Click += this.SearchClicked;

            this.personInput.Name = "personInput";
            this.personInput.Location = new Point(14, 428);
            this.personInput.Size = new Size(420, 28);
            this.personInput.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
            this.personInput.SelectedIndexChanged += this.ChoiceChanged;

            this.roleInput.Name = "roleInput";
            this.roleInput.Location = new Point(446, 428);
            this.roleInput.Size = new Size(128, 28);
            this.roleInput.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
            this.roleInput.Items.AddRange(new RadListDataItem[] {
                new RadListDataItem("Member"), new RadListDataItem("Guest"), new RadListDataItem("Admin") });
            this.roleInput.SelectedIndex = 0;

            this.addButton.Name = "addButton";
            this.addButton.Text = "Add person";
            this.addButton.Location = new Point(587, 427);
            this.addButton.Size = new Size(105, 29);
            this.addButton.Click += this.AddClicked;

            this.changeRoleButton.Name = "changeRoleButton";
            this.changeRoleButton.Text = "Change selected role";
            this.changeRoleButton.Location = new Point(488, 12);
            this.changeRoleButton.Size = new Size(145, 28);
            this.changeRoleButton.Click += this.ChangeRoleClicked;

            this.removeButton.Name = "removeButton";
            this.removeButton.Text = "Remove selected";
            this.removeButton.Location = new Point(643, 12);
            this.removeButton.Size = new Size(129, 28);
            this.removeButton.Click += this.RemoveClicked;

            this.invitationsButton.Name = "invitationsButton";
            this.invitationsButton.Text = "Manage invitations";
            this.invitationsButton.Location = new Point(630, 386);
            this.invitationsButton.Size = new Size(142, 29);
            this.invitationsButton.Click += this.InvitationsClicked;

            this.statusLabel.Name = "statusLabel";
            this.statusLabel.Location = new Point(14, 481);
            this.statusLabel.Size = new Size(630, 34);

            this.closeButton.Name = "closeButton";
            this.closeButton.Text = "Close";
            this.closeButton.Location = new Point(677, 481);
            this.closeButton.Size = new Size(95, 29);
            this.closeButton.DialogResult = DialogResult.Cancel;

            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.ClientSize = new Size(787, 526);
            this.Controls.AddRange(new Control[] {
                this.heading, this.memberGrid, this.searchInput, this.searchButton, this.personInput,
                this.roleInput, this.addButton, this.changeRoleButton, this.removeButton, this.invitationsButton,
                this.statusLabel, this.closeButton });
            this.Font = new Font("Segoe UI", 10F);
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.MaximizeBox = false;
            this.MinimizeBox = false;
            this.Name = "PmsWorkspaceMembersForm";
            this.StartPosition = FormStartPosition.CenterParent;
            this.Text = "Workspace members";
            this.CancelButton = this.closeButton;
            this.Load += this.MembersLoaded;
            ((System.ComponentModel.ISupportInitialize)this.memberGrid.MasterTemplate).EndInit();
            ((System.ComponentModel.ISupportInitialize)this.memberGrid).EndInit();
            this.ResumeLayout(false);
            this.PerformLayout();
        }

        private Label heading;
        private RadGridView memberGrid;
        private GridViewTextBoxColumn nameColumn;
        private GridViewTextBoxColumn emailColumn;
        private GridViewTextBoxColumn roleColumn;
        private GridViewTextBoxColumn statusColumn;
        private RadTextBox searchInput;
        private RadButton searchButton;
        private RadDropDownList personInput;
        private RadDropDownList roleInput;
        private RadButton addButton;
        private RadButton changeRoleButton;
        private RadButton removeButton;
        private RadButton invitationsButton;
        private Label statusLabel;
        private RadButton closeButton;
    }
}
