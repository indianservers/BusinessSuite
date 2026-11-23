#nullable disable
using Telerik.WinControls.UI;

namespace Business_Suite;

partial class CrmQuotationsForm
{
    private void InitializeComponent()
    {
        this.titleLabel = new Label();
        this.searchBox = new CueTextBox();
        this.refreshButton = new Button();
        this.reviewButton = new Button();
        this.newButton = new Button();
        this.editButton = new Button();
        this.feedback = new Label();
        this.quotesGrid = new RadGridView();
        this.quote_numberColumn = new GridViewTextBoxColumn();
        this.customerColumn = new GridViewTextBoxColumn();
        this.dealColumn = new GridViewTextBoxColumn();
        this.statusColumn = new GridViewTextBoxColumn();
        this.version_numberColumn = new GridViewTextBoxColumn();
        this.issue_dateColumn = new GridViewDateTimeColumn();
        this.expiry_dateColumn = new GridViewDateTimeColumn();
        this.currencyColumn = new GridViewTextBoxColumn();
        this.total_amountColumn = new GridViewDecimalColumn();
        ((System.ComponentModel.ISupportInitialize)this.quotesGrid).BeginInit();
        ((System.ComponentModel.ISupportInitialize)this.quotesGrid.MasterTemplate).BeginInit();
        this.SuspendLayout();

        this.titleLabel.Name = "titleLabel";
        this.titleLabel.Location = new Point(21, 15);
        this.titleLabel.Size = new Size(570, 49);
        this.titleLabel.Text = "Quotations";
        this.titleLabel.Font = new Font("Segoe UI Semibold", 24F);
        this.Controls.Add(this.titleLabel);

        this.searchBox.Name = "searchBox";
        this.searchBox.Location = new Point(22, 75);
        this.searchBox.Size = new Size(305, 28);
        this.searchBox.PlaceholderText = "Search number, customer, deal or status";
        this.searchBox.MaxLength = 180;
        this.Controls.Add(this.searchBox);

        this.refreshButton.Name = "refreshButton";
        this.refreshButton.Location = new Point(341, 72);
        this.refreshButton.Size = new Size(116, 35);
        this.refreshButton.Text = "Search / refresh";
        this.refreshButton.Click += this.RefreshClicked;
        this.Controls.Add(this.refreshButton);

        this.reviewButton.Name = "reviewButton";
        this.reviewButton.Location = new Point(469, 72);
        this.reviewButton.Size = new Size(171, 35);
        this.reviewButton.Text = "Review quotation";
        this.reviewButton.Enabled = false;
        this.reviewButton.Click += this.ReviewClicked;
        this.Controls.Add(this.reviewButton);

        this.newButton.Name = "newButton";
        this.newButton.Location = new Point(656, 72);
        this.newButton.Size = new Size(151, 35);
        this.newButton.Text = "New quotation";
        this.newButton.Click += this.NewClicked;
        this.newButton.Enabled = false;
        this.Controls.Add(this.newButton);

        this.editButton.Name = "editButton";
        this.editButton.Location = new Point(818, 72);
        this.editButton.Size = new Size(152, 35);
        this.editButton.Text = "Edit draft";
        this.editButton.Click += this.EditClicked;
        this.editButton.Enabled = false;
        this.Controls.Add(this.editButton);

        this.feedback.Name = "feedback";
        this.feedback.Location = new Point(22, 513);
        this.feedback.Size = new Size(945, 26);
        this.feedback.Anchor = AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
        this.feedback.Text = "Loading quotations…";
        this.Controls.Add(this.feedback);

        this.quotesGrid.Name = "quotesGrid";
        this.quotesGrid.Location = new Point(22, 123);
        this.quotesGrid.Size = new Size(947, 381);
        this.quotesGrid.MasterTemplate.AutoGenerateColumns = false;
        this.quotesGrid.MasterTemplate.AutoSizeColumnsMode = GridViewAutoSizeColumnsMode.Fill;
        this.quotesGrid.MasterTemplate.AllowAddNewRow = false;
        this.quotesGrid.MasterTemplate.AllowDeleteRow = false;
        this.quotesGrid.ShowGroupPanel = false;
        this.quotesGrid.ReadOnly = true;
        this.quotesGrid.Anchor = AnchorStyles.Top | AnchorStyles.Bottom | AnchorStyles.Right | AnchorStyles.Left;
        this.quotesGrid.SelectionChanged += this.SelectionChanged;
        this.Controls.Add(this.quotesGrid);
        this.quote_numberColumn.Name = "quote_number";
        this.quote_numberColumn.FieldName = "quote_number";
        this.quote_numberColumn.HeaderText = "Quotation";
        this.quote_numberColumn.Width = 145;
        this.customerColumn.Name = "customer";
        this.customerColumn.FieldName = "customer";
        this.customerColumn.HeaderText = "Customer";
        this.customerColumn.Width = 125;
        this.dealColumn.Name = "deal";
        this.dealColumn.FieldName = "deal";
        this.dealColumn.HeaderText = "Deal";
        this.dealColumn.Width = 120;
        this.statusColumn.Name = "status";
        this.statusColumn.FieldName = "status";
        this.statusColumn.HeaderText = "Status";
        this.statusColumn.Width = 90;
        this.version_numberColumn.Name = "version_number";
        this.version_numberColumn.FieldName = "version_number";
        this.version_numberColumn.HeaderText = "Version";
        this.version_numberColumn.Width = 52;
        this.issue_dateColumn.Name = "issue_date";
        this.issue_dateColumn.FieldName = "issue_date";
        this.issue_dateColumn.HeaderText = "Issued";
        this.issue_dateColumn.Width = 95;
        this.issue_dateColumn.FormatString = "{0:dd MMM yyyy}";
        this.expiry_dateColumn.Name = "expiry_date";
        this.expiry_dateColumn.FieldName = "expiry_date";
        this.expiry_dateColumn.HeaderText = "Expires";
        this.expiry_dateColumn.Width = 95;
        this.expiry_dateColumn.FormatString = "{0:dd MMM yyyy}";
        this.currencyColumn.Name = "currency";
        this.currencyColumn.FieldName = "currency";
        this.currencyColumn.HeaderText = "Currency";
        this.currencyColumn.Width = 65;
        this.total_amountColumn.Name = "total_amount";
        this.total_amountColumn.FieldName = "total_amount";
        this.total_amountColumn.HeaderText = "Total";
        this.total_amountColumn.Width = 90;
        this.total_amountColumn.FormatString = "{0:N2}";
        this.quotesGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] { this.quote_numberColumn, this.customerColumn, this.dealColumn, this.statusColumn, this.version_numberColumn, this.issue_dateColumn, this.expiry_dateColumn, this.currencyColumn, this.total_amountColumn });
        this.Text = "Business Suite | CRM Quotations";
        this.Name = "CrmQuotationsForm";
        this.ClientSize = new Size(992, 555);
        this.StartPosition = FormStartPosition.CenterParent;
        this.Font = new Font("Segoe UI", 10F);
        this.AutoScaleDimensions = new SizeF(96F, 96F);
        this.AutoScaleMode = AutoScaleMode.Dpi;
        this.BackColor = Color.FromArgb(243, 246, 251);
        this.AcceptButton = this.refreshButton;
        this.MinimumSize = new Size(1000, 500);
        this.Shown += this.WorkspaceShown;
        this.FormClosed += this.WorkspaceClosed;
        ((System.ComponentModel.ISupportInitialize)this.quotesGrid.MasterTemplate).EndInit();
        ((System.ComponentModel.ISupportInitialize)this.quotesGrid).EndInit();
        this.ResumeLayout(false);
        this.PerformLayout();
    }

    private Label titleLabel;
    private CueTextBox searchBox;
    private Button refreshButton;
    private Button reviewButton;
    private Button newButton;
    private Button editButton;
    private Label feedback;
    private RadGridView quotesGrid;
    private GridViewTextBoxColumn quote_numberColumn;
    private GridViewTextBoxColumn customerColumn;
    private GridViewTextBoxColumn dealColumn;
    private GridViewTextBoxColumn statusColumn;
    private GridViewTextBoxColumn version_numberColumn;
    private GridViewDateTimeColumn issue_dateColumn;
    private GridViewDateTimeColumn expiry_dateColumn;
    private GridViewTextBoxColumn currencyColumn;
    private GridViewDecimalColumn total_amountColumn;
}
