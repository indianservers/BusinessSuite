#nullable disable
using System.ComponentModel;
using System.Drawing;
using System.Windows.Forms;
using Telerik.WinControls.UI;

namespace Business_Suite;

partial class EmailTemplateTimelineForm
{
    private void InitializeComponent()
    {
        this.refreshButton = new RadButton();
        this.statusLabel = new Label();
        this.timelineGrid = new RadGridView();
        this.recordedColumn = new GridViewTextBoxColumn();
        this.actionColumn = new GridViewTextBoxColumn();
        this.subjectColumn = new GridViewTextBoxColumn();
        this.summaryColumn = new GridViewTextBoxColumn();
        ((ISupportInitialize)this.refreshButton).BeginInit();
        ((ISupportInitialize)this.timelineGrid).BeginInit();
        ((ISupportInitialize)this.timelineGrid.MasterTemplate).BeginInit();
        this.SuspendLayout();

        this.refreshButton.Name = "refreshButton";
        this.refreshButton.Text = "Refresh";
        this.refreshButton.Location = new Point(16, 16);
        this.refreshButton.Size = new Size(106, 28);
        this.refreshButton.Click += this.RefreshClicked;
        this.statusLabel.Name = "statusLabel";
        this.statusLabel.Anchor = AnchorStyles.Left | AnchorStyles.Bottom | AnchorStyles.Right;
        this.statusLabel.Location = new Point(16, 392);
        this.statusLabel.Size = new Size(741, 28);

        this.timelineGrid.Name = "timelineGrid";
        this.timelineGrid.Location = new Point(16, 54);
        this.timelineGrid.Size = new Size(741, 328);
        this.timelineGrid.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Bottom;
        this.timelineGrid.ReadOnly = true;
        this.timelineGrid.MasterTemplate.AutoGenerateColumns = false;
        this.timelineGrid.MasterTemplate.AllowAddNewRow = false;
        this.timelineGrid.MasterTemplate.AllowDeleteRow = false;
        this.timelineGrid.MasterTemplate.AllowEditRow = false;
        this.timelineGrid.MasterTemplate.AutoSizeColumnsMode = GridViewAutoSizeColumnsMode.Fill;
        this.recordedColumn.Name = "recordedColumn";
        this.recordedColumn.FieldName = "Recorded";
        this.recordedColumn.HeaderText = "Recorded";
        this.recordedColumn.Width = 150;
        this.recordedColumn.FormatString = "{0:g}";
        this.actionColumn.Name = "actionColumn";
        this.actionColumn.FieldName = "Action";
        this.actionColumn.HeaderText = "Action";
        this.actionColumn.Width = 85;
        this.subjectColumn.Name = "subjectColumn";
        this.subjectColumn.FieldName = "Subject";
        this.subjectColumn.HeaderText = "Subject";
        this.subjectColumn.Width = 200;
        this.summaryColumn.Name = "summaryColumn";
        this.summaryColumn.FieldName = "Summary";
        this.summaryColumn.HeaderText = "Summary";
        this.summaryColumn.Width = 255;
        this.timelineGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] {
            this.recordedColumn, this.actionColumn, this.subjectColumn, this.summaryColumn
        });

        this.Controls.Add(this.refreshButton);
        this.Controls.Add(this.statusLabel);
        this.Controls.Add(this.timelineGrid);
        this.AutoScaleDimensions = new SizeF(96F, 96F);
        this.AutoScaleMode = AutoScaleMode.Dpi;
        this.ClientSize = new Size(773, 430);
        this.MinimumSize = new Size(650, 335);
        this.StartPosition = FormStartPosition.CenterParent;
        this.BackColor = Color.FromArgb(243, 246, 251);
        this.Font = new Font("Segoe UI", 10F);
        this.Text = "Template history";
        this.Name = "EmailTemplateTimelineForm";
        this.ShowInTaskbar = false;
        this.Shown += this.RefreshClicked;

        ((ISupportInitialize)this.refreshButton).EndInit();
        ((ISupportInitialize)this.timelineGrid.MasterTemplate).EndInit();
        ((ISupportInitialize)this.timelineGrid).EndInit();
        this.ResumeLayout(false);
    }

    private RadButton refreshButton;
    private Label statusLabel;
    private RadGridView timelineGrid;
    private GridViewTextBoxColumn recordedColumn;
    private GridViewTextBoxColumn actionColumn;
    private GridViewTextBoxColumn subjectColumn;
    private GridViewTextBoxColumn summaryColumn;
}
