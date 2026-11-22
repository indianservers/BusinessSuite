#nullable disable
using System;
using System.Drawing;
using System.Windows.Forms;

namespace Business_Suite
{
    partial class FinanceAndAccountingForm
    {
        private void InitializeComponent()
        {
            this.headingLabel = new Label();
            this.descriptionLabel = new Label();
            this.financeWorkspaceButton = new Button();
            this.ledgersButton = new Button();
            this.workspacesButton = new Button();
            this.SuspendLayout();
            // headingLabel
            this.headingLabel.Location = new Point(24, 24);
            this.headingLabel.Size = new Size(550, 43);
            this.headingLabel.Name = "headingLabel";
            this.headingLabel.Text = "Finance & Accounting";
            this.headingLabel.Font = new Font("Segoe UI Semibold", 21F);
            // descriptionLabel
            this.descriptionLabel.Location = new Point(24, 74);
            this.descriptionLabel.Size = new Size(550, 31);
            this.descriptionLabel.Name = "descriptionLabel";
            this.descriptionLabel.Text = "Accounts, ledgers and financial workspaces.";
            // financeWorkspaceButton
            this.financeWorkspaceButton.Location = new Point(24, 112);
            this.financeWorkspaceButton.Size = new Size(240, 42);
            this.financeWorkspaceButton.Name = "financeWorkspaceButton";
            this.financeWorkspaceButton.Text = "Finance workspace";
            this.financeWorkspaceButton.FlatStyle = FlatStyle.Flat;
            this.financeWorkspaceButton.BackColor = Color.White;
            this.financeWorkspaceButton.UseVisualStyleBackColor = false;
            this.financeWorkspaceButton.TabIndex = 0;
            this.financeWorkspaceButton.Click += this.financeWorkspaceButton_Click;
            // ledgersButton
            this.ledgersButton.Location = new Point(282, 112);
            this.ledgersButton.Size = new Size(240, 42);
            this.ledgersButton.Name = "ledgersButton";
            this.ledgersButton.Text = "Ledgers";
            this.ledgersButton.FlatStyle = FlatStyle.Flat;
            this.ledgersButton.BackColor = Color.White;
            this.ledgersButton.UseVisualStyleBackColor = false;
            this.ledgersButton.TabIndex = 1;
            this.ledgersButton.Click += this.ledgersButton_Click;
            // workspacesButton
            this.workspacesButton.Location = new Point(24, 164);
            this.workspacesButton.Size = new Size(240, 42);
            this.workspacesButton.Name = "workspacesButton";
            this.workspacesButton.Text = "Workspaces";
            this.workspacesButton.FlatStyle = FlatStyle.Flat;
            this.workspacesButton.BackColor = Color.White;
            this.workspacesButton.UseVisualStyleBackColor = false;
            this.workspacesButton.TabIndex = 2;
            this.workspacesButton.Click += this.workspacesButton_Click;
            this.Controls.Add(this.headingLabel);
            this.Controls.Add(this.descriptionLabel);
            this.Controls.Add(this.financeWorkspaceButton);
            this.Controls.Add(this.ledgersButton);
            this.Controls.Add(this.workspacesButton);
            this.AutoScaleDimensions = new SizeF(96F, 96F);
            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.ClientSize = new Size(600, 350);
            this.StartPosition = FormStartPosition.CenterParent;
            this.BackColor = Color.FromArgb(243, 246, 251);
            this.Font = new Font("Segoe UI", 10F);
            this.Text = "Business Suite | Finance & Accounting";
            this.Name = "FinanceAndAccountingForm";
            this.ResumeLayout(false);
            this.PerformLayout();
        }

        private Label headingLabel;
        private Label descriptionLabel;
        private Button financeWorkspaceButton;
        private Button ledgersButton;
        private Button workspacesButton;
    }
}
