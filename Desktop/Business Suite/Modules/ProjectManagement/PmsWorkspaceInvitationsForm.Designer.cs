#nullable disable
using System.Drawing;
using System.Windows.Forms;
using Telerik.WinControls.UI;

namespace Business_Suite
{
    partial class PmsWorkspaceInvitationsForm
    {
        private void InitializeComponent()
        {
            this.heading = new Label();
            this.invitationGrid = new RadGridView();
            this.workspaceColumn = new GridViewTextBoxColumn();
            this.emailColumn = new GridViewTextBoxColumn();
            this.roleColumn = new GridViewTextBoxColumn();
            this.statusColumn = new GridViewTextBoxColumn();
            this.expiresColumn = new GridViewTextBoxColumn();
            this.emailInput = new RadTextBox();
            this.roleInput = new RadDropDownList();
            this.issueButton = new RadButton();
            this.resendButton = new RadButton();
            this.revokeButton = new RadButton();
            this.acceptButton = new RadButton();
            this.closeButton = new RadButton();
            this.statusLabel = new Label();
            ((System.ComponentModel.ISupportInitialize)this.invitationGrid).BeginInit();
            ((System.ComponentModel.ISupportInitialize)this.invitationGrid.MasterTemplate).BeginInit();
            this.SuspendLayout();

            this.heading.Name = "heading";
            this.heading.Location = new Point(14, 12);
            this.heading.Size = new Size(790, 27);
            this.heading.Font = new Font("Segoe UI Semibold", 11F);

            this.workspaceColumn.Name = "workspaceColumn";
            this.workspaceColumn.FieldName = "workspace";
            this.workspaceColumn.HeaderText = "Workspace";
            this.workspaceColumn.Width = 185;

            this.emailColumn.Name = "emailColumn";
            this.emailColumn.FieldName = "email";
            this.emailColumn.HeaderText = "Recipient";
            this.emailColumn.Width = 248;

            this.roleColumn.Name = "roleColumn";
            this.roleColumn.FieldName = "role";
            this.roleColumn.HeaderText = "Role";
            this.roleColumn.Width = 100;

            this.statusColumn.Name = "statusColumn";
            this.statusColumn.FieldName = "status";
            this.statusColumn.HeaderText = "Status";
            this.statusColumn.Width = 105;

            this.expiresColumn.Name = "expiresColumn";
            this.expiresColumn.FieldName = "expires_at";
            this.expiresColumn.HeaderText = "Expires (UTC)";
            this.expiresColumn.Width = 132;
            this.expiresColumn.FormatString = "{0:g}";
            this.invitationGrid.Name = "invitationGrid";
            this.invitationGrid.Location = new Point(14, 43);
            this.invitationGrid.Size = new Size(795, 272);
            this.invitationGrid.AutoGenerateColumns = false;
            this.invitationGrid.ReadOnly = true;
            this.invitationGrid.MasterTemplate.AllowAddNewRow = false;
            this.invitationGrid.MasterTemplate.AllowDeleteRow = false;
            this.invitationGrid.MasterTemplate.AllowEditRow = false;
            this.invitationGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] {
                this.workspaceColumn, this.emailColumn, this.roleColumn, this.statusColumn, this.expiresColumn });
            this.invitationGrid.CurrentRowChanged += this.InvitationChanged;

            this.emailInput.Name = "emailInput";
            this.emailInput.NullText = "Invite email address";
            this.emailInput.Location = new Point(14, 329);
            this.emailInput.Size = new Size(286, 25);
            this.emailInput.MaxLength = 100;
            this.emailInput.TextChanged += this.EmailChanged;

            this.roleInput.Name = "roleInput";
            this.roleInput.Location = new Point(312, 329);
            this.roleInput.Size = new Size(108, 25);
            this.roleInput.DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList;
            this.roleInput.Items.AddRange(new RadListDataItem[] {
                new RadListDataItem("Member"), new RadListDataItem("Guest"), new RadListDataItem("Admin") });
            this.roleInput.SelectedIndex = 0;

            this.issueButton.Name = "issueButton";
            this.issueButton.Text = "Create invitation";
            this.issueButton.Location = new Point(430, 326);
            this.issueButton.Size = new Size(122, 29);
            this.issueButton.Click += this.IssueClicked;

            this.resendButton.Name = "resendButton";
            this.resendButton.Text = "Replace selected";
            this.resendButton.Location = new Point(560, 326);
            this.resendButton.Size = new Size(116, 29);
            this.resendButton.Click += this.ResendClicked;

            this.revokeButton.Name = "revokeButton";
            this.revokeButton.Text = "Revoke selected";
            this.revokeButton.Location = new Point(684, 326);
            this.revokeButton.Size = new Size(125, 29);
            this.revokeButton.Click += this.RevokeClicked;

            this.acceptButton.Name = "acceptButton";
            this.acceptButton.Text = "Accept invitation";
            this.acceptButton.Location = new Point(14, 326);
            this.acceptButton.Size = new Size(137, 29);
            this.acceptButton.Click += this.AcceptClicked;

            this.statusLabel.Name = "statusLabel";
            this.statusLabel.Location = new Point(14, 367);
            this.statusLabel.Size = new Size(676, 48);

            this.closeButton.Name = "closeButton";
            this.closeButton.Text = "Close";
            this.closeButton.Location = new Point(713, 382);
            this.closeButton.Size = new Size(96, 29);
            this.closeButton.DialogResult = DialogResult.Cancel;

            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.ClientSize = new Size(824, 426);
            this.Controls.AddRange(new Control[] {
                this.heading, this.invitationGrid, this.emailInput, this.roleInput, this.issueButton,
                this.resendButton, this.revokeButton, this.acceptButton, this.statusLabel, this.closeButton });
            this.Font = new Font("Segoe UI", 10F);
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.MaximizeBox = false;
            this.MinimizeBox = false;
            this.Name = "PmsWorkspaceInvitationsForm";
            this.StartPosition = FormStartPosition.CenterParent;
            this.Text = "Workspace invitations";
            this.CancelButton = this.closeButton;
            this.Load += this.InvitationsLoaded;
            ((System.ComponentModel.ISupportInitialize)this.invitationGrid.MasterTemplate).EndInit();
            ((System.ComponentModel.ISupportInitialize)this.invitationGrid).EndInit();
            this.ResumeLayout(false);
            this.PerformLayout();
        }

        private Label heading;
        private RadGridView invitationGrid;
        private GridViewTextBoxColumn workspaceColumn;
        private GridViewTextBoxColumn emailColumn;
        private GridViewTextBoxColumn roleColumn;
        private GridViewTextBoxColumn statusColumn;
        private GridViewTextBoxColumn expiresColumn;
        private RadTextBox emailInput;
        private RadDropDownList roleInput;
        private RadButton issueButton;
        private RadButton resendButton;
        private RadButton revokeButton;
        private RadButton acceptButton;
        private Label statusLabel;
        private RadButton closeButton;
    }
}
