#nullable disable
using System;
using System.Drawing;
using System.Windows.Forms;

namespace Business_Suite
{
    partial class PowerAppsForm
    {
        private void InitializeComponent()
        {
            this.headingLabel = new Label();
            this.descriptionLabel = new Label();
            this.powerAppsButton = new Button();
            this.automationsButton = new Button();
            this.approvalsButton = new Button();
            this.SuspendLayout();
            // headingLabel
            this.headingLabel.Location = new Point(24, 24);
            this.headingLabel.Size = new Size(550, 43);
            this.headingLabel.Name = "headingLabel";
            this.headingLabel.Text = "Power Apps";
            this.headingLabel.Font = new Font("Segoe UI Semibold", 21F);
            // descriptionLabel
            this.descriptionLabel.Location = new Point(24, 74);
            this.descriptionLabel.Size = new Size(550, 31);
            this.descriptionLabel.Name = "descriptionLabel";
            this.descriptionLabel.Text = "Apps, automations and approvals.";
            // powerAppsButton
            this.powerAppsButton.Location = new Point(24, 112);
            this.powerAppsButton.Size = new Size(240, 42);
            this.powerAppsButton.Name = "powerAppsButton";
            this.powerAppsButton.Text = "Power Apps";
            this.powerAppsButton.FlatStyle = FlatStyle.Flat;
            this.powerAppsButton.BackColor = Color.White;
            this.powerAppsButton.UseVisualStyleBackColor = false;
            this.powerAppsButton.TabIndex = 0;
            this.powerAppsButton.Click += this.powerAppsButton_Click;
            // automationsButton
            this.automationsButton.Location = new Point(282, 112);
            this.automationsButton.Size = new Size(240, 42);
            this.automationsButton.Name = "automationsButton";
            this.automationsButton.Text = "Automations";
            this.automationsButton.FlatStyle = FlatStyle.Flat;
            this.automationsButton.BackColor = Color.White;
            this.automationsButton.UseVisualStyleBackColor = false;
            this.automationsButton.TabIndex = 1;
            this.automationsButton.Click += this.automationsButton_Click;
            // approvalsButton
            this.approvalsButton.Location = new Point(24, 164);
            this.approvalsButton.Size = new Size(240, 42);
            this.approvalsButton.Name = "approvalsButton";
            this.approvalsButton.Text = "Approvals";
            this.approvalsButton.FlatStyle = FlatStyle.Flat;
            this.approvalsButton.BackColor = Color.White;
            this.approvalsButton.UseVisualStyleBackColor = false;
            this.approvalsButton.TabIndex = 2;
            this.approvalsButton.Click += this.approvalsButton_Click;
            this.Controls.Add(this.headingLabel);
            this.Controls.Add(this.descriptionLabel);
            this.Controls.Add(this.powerAppsButton);
            this.Controls.Add(this.automationsButton);
            this.Controls.Add(this.approvalsButton);
            this.AutoScaleDimensions = new SizeF(96F, 96F);
            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.ClientSize = new Size(600, 350);
            this.StartPosition = FormStartPosition.CenterParent;
            this.BackColor = Color.FromArgb(243, 246, 251);
            this.Font = new Font("Segoe UI", 10F);
            this.Text = "Business Suite | Power Apps";
            this.Name = "PowerAppsForm";
            this.ResumeLayout(false);
            this.PerformLayout();
        }

        private Label headingLabel;
        private Label descriptionLabel;
        private Button powerAppsButton;
        private Button automationsButton;
        private Button approvalsButton;
    }
}
