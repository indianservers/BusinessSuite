#nullable disable
using System;
using System.Drawing;
using System.Windows.Forms;

namespace Business_Suite
{
    partial class BusinessComparisonWindow
    {
        private void InitializeComponent()
        {
            this.introLabel = new Label();
            this.grid = new DataGridView();
            this.areaColumn = new DataGridViewTextBoxColumn();
            this.keyColumn = new DataGridViewTextBoxColumn();
            this.statusColumn = new DataGridViewTextBoxColumn();
            this.localLabel = new Label();
            this.serverLabel = new Label();
            this.local = new TextBox();
            this.server = new TextBox();
            this.errors = new TextBox();
            ((System.ComponentModel.ISupportInitialize)this.grid).BeginInit();
            this.SuspendLayout();
            // introLabel
            this.introLabel.Location = new Point(20, 20);
            this.introLabel.Size = new Size(980, 44);
            this.introLabel.Name = "introLabel";
            this.introLabel.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            this.introLabel.Text = "Review possible matches among the records both accounts can access. This preview does not merge records.";
            // grid
            this.grid.Location = new Point(20, 72);
            this.grid.Size = new Size(980, 300);
            this.grid.Name = "grid";
            this.grid.Anchor = AnchorStyles.Top | AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
            this.grid.ReadOnly = true;
            this.grid.AllowUserToAddRows = false;
            this.grid.AllowUserToDeleteRows = false;
            this.grid.MultiSelect = false;
            this.grid.SelectionMode = DataGridViewSelectionMode.FullRowSelect;
            this.grid.RowHeadersVisible = false;
            this.grid.BackgroundColor = Color.White;
            this.grid.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill;
            this.grid.AutoGenerateColumns = false;
            this.grid.SelectionChanged += this.PopulateDetails;
            // areaColumn
            this.areaColumn.Name = "AreaColumn";
            this.areaColumn.DataPropertyName = "Area";
            this.areaColumn.HeaderText = "Area";
            // keyColumn
            this.keyColumn.Name = "KeyColumn";
            this.keyColumn.DataPropertyName = "Key";
            this.keyColumn.HeaderText = "Match key";
            // statusColumn
            this.statusColumn.Name = "StatusColumn";
            this.statusColumn.DataPropertyName = "Status";
            this.statusColumn.HeaderText = "Comparison";
            // localLabel
            this.localLabel.Location = new Point(20, 385);
            this.localLabel.Size = new Size(300, 26);
            this.localLabel.Name = "localLabel";
            this.localLabel.Text = "Local record";
            this.localLabel.Anchor = AnchorStyles.Bottom | AnchorStyles.Left;
            // serverLabel
            this.serverLabel.Location = new Point(518, 385);
            this.serverLabel.Size = new Size(300, 26);
            this.serverLabel.Name = "serverLabel";
            this.serverLabel.Text = "Server record";
            this.serverLabel.Anchor = AnchorStyles.Bottom | AnchorStyles.Right;
            // local
            this.local.Location = new Point(20, 416);
            this.local.Size = new Size(482, 166);
            this.local.Name = "local";
            this.local.AccessibleName = "Local record";
            this.local.Multiline = true;
            this.local.ReadOnly = true;
            this.local.ScrollBars = ScrollBars.Vertical;
            this.local.Anchor = AnchorStyles.Bottom | AnchorStyles.Left;
            // server
            this.server.Location = new Point(518, 416);
            this.server.Size = new Size(482, 166);
            this.server.Name = "server";
            this.server.AccessibleName = "Server record";
            this.server.Multiline = true;
            this.server.ReadOnly = true;
            this.server.ScrollBars = ScrollBars.Vertical;
            this.server.Anchor = AnchorStyles.Bottom | AnchorStyles.Right;
            // errors
            this.errors.Location = new Point(20, 599);
            this.errors.Size = new Size(980, 64);
            this.errors.Name = "errors";
            this.errors.AccessibleName = "Areas unavailable for comparison";
            this.errors.Multiline = true;
            this.errors.ReadOnly = true;
            this.errors.ScrollBars = ScrollBars.Vertical;
            this.errors.Anchor = AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
            this.grid.Columns.AddRange(new DataGridViewColumn[] { this.areaColumn, this.keyColumn, this.statusColumn });
            this.Shown += this.PopulateDetails;
            this.Controls.Add(this.introLabel);
            this.Controls.Add(this.grid);
            this.Controls.Add(this.localLabel);
            this.Controls.Add(this.serverLabel);
            this.Controls.Add(this.local);
            this.Controls.Add(this.server);
            this.Controls.Add(this.errors);
            this.AutoScaleDimensions = new SizeF(96F, 96F);
            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.Font = new Font("Segoe UI", 10F);
            this.BackColor = Color.FromArgb(243, 246, 251);
            this.ForeColor = Color.FromArgb(24, 35, 58);
            this.Text = "Business Suite | Compare business records";
            this.ClientSize = new Size(1020, 690);
            this.MinimumSize = new Size(1036, 729);
            this.StartPosition = FormStartPosition.CenterParent;
            this.Name = "BusinessComparisonWindow";
            ((System.ComponentModel.ISupportInitialize)this.grid).EndInit();
            this.ResumeLayout(false);
            this.PerformLayout();
        }

        private Label introLabel;
        private DataGridView grid;
        private DataGridViewTextBoxColumn areaColumn;
        private DataGridViewTextBoxColumn keyColumn;
        private DataGridViewTextBoxColumn statusColumn;
        private Label localLabel;
        private Label serverLabel;
        private TextBox local;
        private TextBox server;
        private TextBox errors;
    }
}
