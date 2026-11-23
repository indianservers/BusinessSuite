#nullable disable
using System.ComponentModel;
using System.Drawing;
using System.Windows.Forms;
using Telerik.WinControls.UI;

namespace Business_Suite;

partial class CommunicationDraftListForm
{
    private void InitializeComponent()
    {
        this.searchBox = new RadTextBox();
        this.refreshButton = new RadButton();
        this.draftGrid = new RadGridView();
        this.bodyLabel = new Label();
        this.bodyBox = new RadTextBox();
        this.statusLabel = new Label();
        this.recordColumn = new GridViewTextBoxColumn();
        this.recipientColumn = new GridViewTextBoxColumn();
        this.subjectColumn = new GridViewTextBoxColumn();
        this.createdColumn = new GridViewTextBoxColumn();
        ((ISupportInitialize)this.searchBox).BeginInit();
        ((ISupportInitialize)this.refreshButton).BeginInit();
        ((ISupportInitialize)this.draftGrid).BeginInit();
        ((ISupportInitialize)this.draftGrid.MasterTemplate).BeginInit();
        ((ISupportInitialize)this.bodyBox).BeginInit();
        this.SuspendLayout();

        this.searchBox.Name = "searchBox";
        this.searchBox.Location = new Point(16, 16);
        this.searchBox.Size = new Size(280, 28);
        this.searchBox.NullText = "Search subject, recipient or CRM record";
        this.searchBox.AccessibleName = "Search email drafts";
        this.searchBox.MaxLength = 240;
        this.refreshButton.Name = "refreshButton";
        this.refreshButton.Text = "Refresh";
        this.refreshButton.Location = new Point(304, 16);
        this.refreshButton.Size = new Size(106, 28);
        this.refreshButton.Click += this.RefreshClicked;
        this.bodyLabel.Name = "bodyLabel";
        this.bodyLabel.Text = "Message";
        this.bodyLabel.Location = new Point(16, 330);
        this.bodyLabel.Size = new Size(740, 25);
        this.bodyBox.Name = "bodyBox";
        this.bodyBox.AccessibleName = "Selected draft message";
        this.bodyBox.Location = new Point(16, 356);
        this.bodyBox.Size = new Size(780, 200);
        this.bodyBox.Anchor = AnchorStyles.Top | AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
        this.bodyBox.Multiline = true;
        this.bodyBox.ReadOnly = true;
        this.bodyBox.ScrollBars = ScrollBars.Vertical;
        this.statusLabel.Name = "statusLabel";
        this.statusLabel.Anchor = AnchorStyles.Left | AnchorStyles.Bottom | AnchorStyles.Right;
        this.statusLabel.Location = new Point(16, 565);
        this.statusLabel.Size = new Size(780, 28);

        this.draftGrid.Name = "draftGrid";
        this.draftGrid.Location = new Point(16, 54);
        this.draftGrid.Size = new Size(780, 263);
        this.draftGrid.Anchor = AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Top;
        this.draftGrid.ReadOnly = true;
        this.draftGrid.MasterTemplate.AutoGenerateColumns = false;
        this.draftGrid.MasterTemplate.AllowAddNewRow = false;
        this.draftGrid.MasterTemplate.AllowDeleteRow = false;
        this.draftGrid.MasterTemplate.AllowEditRow = false;
        this.draftGrid.MasterTemplate.AutoSizeColumnsMode = GridViewAutoSizeColumnsMode.Fill;
        this.recordColumn.Name = "recordColumn";
        this.recordColumn.FieldName = "Record";
        this.recordColumn.HeaderText = "CRM record";
        this.recordColumn.Width = 200;
        this.recipientColumn.Name = "recipientColumn";
        this.recipientColumn.FieldName = "Recipient";
        this.recipientColumn.HeaderText = "Recipient email";
        this.recipientColumn.Width = 185;
        this.subjectColumn.Name = "subjectColumn";
        this.subjectColumn.FieldName = "Subject";
        this.subjectColumn.HeaderText = "Subject";
        this.subjectColumn.Width = 240;
        this.createdColumn.Name = "createdColumn";
        this.createdColumn.FieldName = "Created";
        this.createdColumn.HeaderText = "Created";
        this.createdColumn.Width = 135;
        this.createdColumn.FormatString = "{0:g}";
        this.draftGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] {
            this.recordColumn, this.recipientColumn, this.subjectColumn, this.createdColumn
        });
        this.draftGrid.SelectionChanged += this.SelectionChanged;

        this.Controls.Add(this.searchBox);
        this.Controls.Add(this.refreshButton);
        this.Controls.Add(this.draftGrid);
        this.Controls.Add(this.bodyLabel);
        this.Controls.Add(this.bodyBox);
        this.Controls.Add(this.statusLabel);
        this.AcceptButton = this.refreshButton;
        this.AutoScaleDimensions = new SizeF(96F, 96F);
        this.AutoScaleMode = AutoScaleMode.Dpi;
        this.ClientSize = new Size(812, 605);
        this.MinimumSize = new Size(695, 520);
        this.StartPosition = FormStartPosition.CenterParent;
        this.ShowInTaskbar = false;
        this.BackColor = Color.FromArgb(243, 246, 251);
        this.Font = new Font("Segoe UI", 10F);
        this.Text = "Email drafts";
        this.Name = "CommunicationDraftListForm";
        this.Shown += this.RefreshClicked;
        ((ISupportInitialize)this.searchBox).EndInit();
        ((ISupportInitialize)this.refreshButton).EndInit();
        ((ISupportInitialize)this.draftGrid.MasterTemplate).EndInit();
        ((ISupportInitialize)this.draftGrid).EndInit();
        ((ISupportInitialize)this.bodyBox).EndInit();
        this.ResumeLayout(false);
        this.PerformLayout();
    }

    private RadTextBox searchBox;
    private RadButton refreshButton;
    private RadGridView draftGrid;
    private Label bodyLabel;
    private RadTextBox bodyBox;
    private Label statusLabel;
    private GridViewTextBoxColumn recordColumn;
    private GridViewTextBoxColumn recipientColumn;
    private GridViewTextBoxColumn subjectColumn;
    private GridViewTextBoxColumn createdColumn;
}
