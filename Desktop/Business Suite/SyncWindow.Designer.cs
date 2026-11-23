#nullable disable
using System;
using System.Drawing;
using System.Windows.Forms;

namespace Business_Suite
{
    partial class SyncWindow
    {
        private void InitializeComponent()
        {
            this.headingLabel = new Label();
            this.descriptionLabel = new Label();
            this.localLabel = new Label();
            this.websiteLabel = new Label();
            this.localEmail = new CueTextBox();
            this.localPassword = new CueTextBox();
            this.remoteEmail = new CueTextBox();
            this.remotePassword = new CueTextBox();
            this.run = new Button();
            this.status = new Label();
            this.reviewLabel = new Label();
            this.conflicts = new ListBox();
            this.localVersionLabel = new Label();
            this.serverVersionLabel = new Label();
            this.localPreview = new TextBox();
            this.serverPreview = new TextBox();
            this.keepLocal = new Button();
            this.keepServer = new Button();
            this.compare = new Button();
            this.SuspendLayout();
            // headingLabel
            this.headingLabel.Location = new Point(24, 18);
            this.headingLabel.Size = new Size(810, 40);
            this.headingLabel.Name = "headingLabel";
            this.headingLabel.Text = "Sync personal notes";
            this.headingLabel.Font = new Font("Segoe UI Semibold", 22F);
            // descriptionLabel
            this.descriptionLabel.Location = new Point(25, 63);
            this.descriptionLabel.Size = new Size(810, 24);
            this.descriptionLabel.Name = "descriptionLabel";
            this.descriptionLabel.Text = "Copy new standalone private notes. Review changes before replacing an existing note.";
            // localLabel
            this.localLabel.Location = new Point(24, 106);
            this.localLabel.Size = new Size(394, 25);
            this.localLabel.Name = "localLabel";
            this.localLabel.Text = "Local workspace";
            this.localLabel.Font = new Font("Segoe UI Semibold", 12F);
            // websiteLabel
            this.websiteLabel.Location = new Point(452, 106);
            this.websiteLabel.Size = new Size(394, 25);
            this.websiteLabel.Name = "websiteLabel";
            this.websiteLabel.Text = "Company website";
            this.websiteLabel.Font = new Font("Segoe UI Semibold", 12F);
            // localEmail
            this.localEmail.Location = new Point(24, 136);
            this.localEmail.Size = new Size(394, 32);
            this.localEmail.Name = "localEmail";
            this.localEmail.AccessibleName = "Local email";
            this.localEmail.PlaceholderText = "Local email";
            this.localEmail.UseSystemPasswordChar = false;
            this.localEmail.MaxLength = 254;
            // localPassword
            this.localPassword.Location = new Point(24, 173);
            this.localPassword.Size = new Size(394, 32);
            this.localPassword.Name = "localPassword";
            this.localPassword.AccessibleName = "Local password";
            this.localPassword.PlaceholderText = "Local password";
            this.localPassword.UseSystemPasswordChar = true;
            this.localPassword.MaxLength = 128;
            // remoteEmail
            this.remoteEmail.Location = new Point(452, 136);
            this.remoteEmail.Size = new Size(394, 32);
            this.remoteEmail.Name = "remoteEmail";
            this.remoteEmail.AccessibleName = "Company email";
            this.remoteEmail.PlaceholderText = "Company email";
            this.remoteEmail.UseSystemPasswordChar = false;
            this.remoteEmail.MaxLength = 254;
            // remotePassword
            this.remotePassword.Location = new Point(452, 173);
            this.remotePassword.Size = new Size(394, 32);
            this.remotePassword.Name = "remotePassword";
            this.remotePassword.AccessibleName = "Company password";
            this.remotePassword.PlaceholderText = "Company password";
            this.remotePassword.UseSystemPasswordChar = true;
            this.remotePassword.MaxLength = 128;
            // run
            this.run.Location = new Point(696, 214);
            this.run.Size = new Size(150, 42);
            this.run.Name = "run";
            this.run.Text = "Sync notes";
            this.run.FlatStyle = FlatStyle.Flat;
            this.run.UseVisualStyleBackColor = false;
            this.run.BackColor = Color.FromArgb(47, 79, 217);
            this.run.ForeColor = Color.White;
            this.run.Click += this.Run_Click;
            // status
            this.status.Location = new Point(24, 215);
            this.status.Size = new Size(650, 39);
            this.status.Name = "status";
            this.status.Text = "Start the local workspace before signing in and syncing.";
            this.status.TextAlign = ContentAlignment.MiddleLeft;
            // reviewLabel
            this.reviewLabel.Location = new Point(24, 269);
            this.reviewLabel.Size = new Size(822, 24);
            this.reviewLabel.Name = "reviewLabel";
            this.reviewLabel.Text = "Changes to review";
            this.reviewLabel.Font = new Font("Segoe UI Semibold", 12F);
            // conflicts
            this.conflicts.Location = new Point(24, 301);
            this.conflicts.Size = new Size(822, 86);
            this.conflicts.Name = "conflicts";
            this.conflicts.AccessibleName = "Notes with conflicts";
            this.conflicts.SelectedIndexChanged += this.Conflicts_SelectedIndexChanged;
            // localVersionLabel
            this.localVersionLabel.Location = new Point(24, 394);
            this.localVersionLabel.Size = new Size(394, 24);
            this.localVersionLabel.Name = "localVersionLabel";
            this.localVersionLabel.Text = "Local version";
            // serverVersionLabel
            this.serverVersionLabel.Location = new Point(452, 394);
            this.serverVersionLabel.Size = new Size(394, 24);
            this.serverVersionLabel.Name = "serverVersionLabel";
            this.serverVersionLabel.Text = "Server version";
            // localPreview
            this.localPreview.Location = new Point(24, 421);
            this.localPreview.Size = new Size(394, 146);
            this.localPreview.Name = "localPreview";
            this.localPreview.AccessibleName = "Local note version";
            this.localPreview.Multiline = true;
            this.localPreview.ReadOnly = true;
            this.localPreview.ScrollBars = ScrollBars.Vertical;
            // serverPreview
            this.serverPreview.Location = new Point(452, 421);
            this.serverPreview.Size = new Size(394, 146);
            this.serverPreview.Name = "serverPreview";
            this.serverPreview.AccessibleName = "Server note version";
            this.serverPreview.Multiline = true;
            this.serverPreview.ReadOnly = true;
            this.serverPreview.ScrollBars = ScrollBars.Vertical;
            // keepLocal
            this.keepLocal.Location = new Point(490, 584);
            this.keepLocal.Size = new Size(166, 42);
            this.keepLocal.Name = "keepLocal";
            this.keepLocal.Text = "Keep local version";
            this.keepLocal.FlatStyle = FlatStyle.Flat;
            this.keepLocal.UseVisualStyleBackColor = false;
            this.keepLocal.BackColor = Color.White;
            this.keepLocal.ForeColor = Color.FromArgb(24, 35, 58);
            this.keepLocal.Click += this.KeepLocal_Click;
            // keepServer
            this.keepServer.Location = new Point(670, 584);
            this.keepServer.Size = new Size(176, 42);
            this.keepServer.Name = "keepServer";
            this.keepServer.Text = "Keep server version";
            this.keepServer.FlatStyle = FlatStyle.Flat;
            this.keepServer.UseVisualStyleBackColor = false;
            this.keepServer.BackColor = Color.White;
            this.keepServer.ForeColor = Color.FromArgb(24, 35, 58);
            this.keepServer.Click += this.KeepServer_Click;
            // compare
            this.compare.Location = new Point(24, 584);
            this.compare.Size = new Size(232, 42);
            this.compare.Name = "compare";
            this.compare.Text = "Compare business records";
            this.compare.FlatStyle = FlatStyle.Flat;
            this.compare.UseVisualStyleBackColor = false;
            this.compare.BackColor = Color.White;
            this.compare.ForeColor = Color.FromArgb(24, 35, 58);
            this.compare.Click += this.Compare_Click;
            this.FormClosing += this.SyncWindow_FormClosing;
            this.FormClosed += this.SyncWindow_FormClosed;
            this.Controls.Add(this.headingLabel);
            this.Controls.Add(this.descriptionLabel);
            this.Controls.Add(this.localLabel);
            this.Controls.Add(this.websiteLabel);
            this.Controls.Add(this.localEmail);
            this.Controls.Add(this.localPassword);
            this.Controls.Add(this.remoteEmail);
            this.Controls.Add(this.remotePassword);
            this.Controls.Add(this.run);
            this.Controls.Add(this.status);
            this.Controls.Add(this.reviewLabel);
            this.Controls.Add(this.conflicts);
            this.Controls.Add(this.localVersionLabel);
            this.Controls.Add(this.serverVersionLabel);
            this.Controls.Add(this.localPreview);
            this.Controls.Add(this.serverPreview);
            this.Controls.Add(this.keepLocal);
            this.Controls.Add(this.keepServer);
            this.Controls.Add(this.compare);
            this.AutoScaleDimensions = new SizeF(96F, 96F);
            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.Font = new Font("Segoe UI", 10F);
            this.BackColor = Color.FromArgb(243, 246, 251);
            this.ForeColor = Color.FromArgb(24, 35, 58);
            this.StartPosition = FormStartPosition.CenterParent;
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.MaximizeBox = false;
            this.MinimizeBox = false;
            this.Text = "Business Suite | Sync and compare";
            this.ClientSize = new Size(870, 648);
            this.AcceptButton = this.run;
            this.Name = "SyncWindow";
            this.ResumeLayout(false);
            this.PerformLayout();
        }

        private Label headingLabel;
        private Label descriptionLabel;
        private Label localLabel;
        private Label websiteLabel;
        private CueTextBox localEmail;
        private CueTextBox localPassword;
        private CueTextBox remoteEmail;
        private CueTextBox remotePassword;
        private Button run;
        private Label status;
        private Label reviewLabel;
        private ListBox conflicts;
        private Label localVersionLabel;
        private Label serverVersionLabel;
        private TextBox localPreview;
        private TextBox serverPreview;
        private Button keepLocal;
        private Button keepServer;
        private Button compare;
    }
}
