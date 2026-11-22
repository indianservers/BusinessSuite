#nullable disable
using System;
using System.Drawing;
using System.Windows.Forms;
using Telerik.WinControls.UI;

namespace Business_Suite
{
    partial class CompaniesGridForm
    {
        private void InitializeComponent()
        {
            this.headingLabel = new Label();
            this.descriptionLabel = new Label();
            this.grid = new RadGridView();
            this.idColumn = new GridViewTextBoxColumn();
            this.nameColumn = new GridViewTextBoxColumn();
            this.activeColumn = new GridViewCheckBoxColumn();
            this.status = new Label();
            this.refresh = new Button();
            ((System.ComponentModel.ISupportInitialize)this.grid).BeginInit();
            ((System.ComponentModel.ISupportInitialize)this.grid.MasterTemplate).BeginInit();
            this.SuspendLayout();
            // headingLabel
            this.headingLabel.Location = new Point(30, 27);
            this.headingLabel.Size = new Size(850, 50);
            this.headingLabel.Name = "headingLabel";
            this.headingLabel.Text = "Local companies";
            this.headingLabel.Font = new Font("Segoe UI Semibold", 27F);
            // descriptionLabel
            this.descriptionLabel.Location = new Point(30, 78);
            this.descriptionLabel.Size = new Size(850, 32);
            this.descriptionLabel.Name = "descriptionLabel";
            this.descriptionLabel.Text = "Company records from Business Suite · PostgreSQL";
            this.descriptionLabel.ForeColor = Color.FromArgb(84, 100, 124);
            // grid
            this.grid.Location = new Point(30, 120);
            this.grid.Size = new Size(860, 334);
            this.grid.Name = "grid";
            this.grid.Anchor = AnchorStyles.Top | AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
            this.grid.MasterTemplate.AllowAddNewRow = false;
            this.grid.MasterTemplate.AllowDeleteRow = false;
            this.grid.MasterTemplate.AutoGenerateColumns = false;
            this.grid.MasterTemplate.AutoSizeColumnsMode = GridViewAutoSizeColumnsMode.Fill;
            this.grid.MasterTemplate.EnableFiltering = true;
            this.grid.ReadOnly = true;
            this.grid.ShowGroupPanel = false;
            // idColumn
            this.idColumn.Name = "id";
            this.idColumn.FieldName = "id";
            this.idColumn.HeaderText = "Company ID";
            this.idColumn.Width = 110;
            // nameColumn
            this.nameColumn.Name = "name";
            this.nameColumn.FieldName = "name";
            this.nameColumn.HeaderText = "Company name";
            this.nameColumn.Width = 570;
            // activeColumn
            this.activeColumn.Name = "is_active";
            this.activeColumn.FieldName = "is_active";
            this.activeColumn.HeaderText = "Active";
            this.activeColumn.Width = 100;
            // status
            this.status.Location = new Point(30, 459);
            this.status.Size = new Size(730, 44);
            this.status.Name = "status";
            this.status.Anchor = AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
            this.status.TextAlign = ContentAlignment.MiddleLeft;
            // refresh
            this.refresh.Location = new Point(786, 460);
            this.refresh.Size = new Size(104, 40);
            this.refresh.Name = "refresh";
            this.refresh.Anchor = AnchorStyles.Bottom | AnchorStyles.Right;
            this.refresh.Text = "Refresh";
            this.refresh.Click += this.LoadCompanies;
            this.grid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] { this.idColumn, this.nameColumn, this.activeColumn });
            this.Shown += this.LoadCompanies;
            this.FormClosed += this.CancelLoad;
            this.Controls.Add(this.headingLabel);
            this.Controls.Add(this.descriptionLabel);
            this.Controls.Add(this.grid);
            this.Controls.Add(this.status);
            this.Controls.Add(this.refresh);
            this.AutoScaleDimensions = new SizeF(96F, 96F);
            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.BackColor = Color.FromArgb(243, 246, 251);
            this.Font = new Font("Segoe UI", 10F);
            this.Text = "Business Suite | Local companies";
            this.ClientSize = new Size(920, 530);
            this.MinimumSize = new Size(640, 390);
            this.StartPosition = FormStartPosition.CenterParent;
            this.Name = "CompaniesGridForm";
            ((System.ComponentModel.ISupportInitialize)this.grid.MasterTemplate).EndInit();
            ((System.ComponentModel.ISupportInitialize)this.grid).EndInit();
            this.ResumeLayout(false);
            this.PerformLayout();
        }

        private Label headingLabel;
        private Label descriptionLabel;
        private RadGridView grid;
        private GridViewTextBoxColumn idColumn;
        private GridViewTextBoxColumn nameColumn;
        private GridViewCheckBoxColumn activeColumn;
        private Label status;
        private Button refresh;
    }
}
