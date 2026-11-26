using System.ComponentModel;
using System.Drawing.Printing;
using Telerik.WinControls.UI;

namespace Business_Suite;

partial class PosReceiptHistoryForm
{
    private void InitializeComponent()
    {
        this.headingLabel = new Label();
        this.statusLabel = new Label();
        this.searchBox = new RadTextBox();
        this.refreshButton = new RadButton();
        this.receiptBox = new RadTextBox();
        this.exportButton = new RadButton();
        this.printButton = new RadButton();
        this.copyButton = new RadButton();
        this.closeButton = new RadButton();
        this.receiptGrid = new RadGridView();
        this.fileDialog = new SaveFileDialog();
        this.printDialog = new PrintDialog();
        this.receiptDocument = new PrintDocument();
        this.invoiceColumn = new GridViewTextBoxColumn();
        this.customerColumn = new GridViewTextBoxColumn();
        this.postedColumn = new GridViewDateTimeColumn();
        this.totalColumn = new GridViewDecimalColumn();
        this.paidColumn = new GridViewDecimalColumn();
        this.dueColumn = new GridViewDecimalColumn();
        ((ISupportInitialize)this.searchBox).BeginInit();
        ((ISupportInitialize)this.refreshButton).BeginInit();
        ((ISupportInitialize)this.receiptBox).BeginInit();
        ((ISupportInitialize)this.exportButton).BeginInit();
        ((ISupportInitialize)this.printButton).BeginInit();
        ((ISupportInitialize)this.copyButton).BeginInit();
        ((ISupportInitialize)this.closeButton).BeginInit();
        ((ISupportInitialize)this.receiptGrid).BeginInit();
        ((ISupportInitialize)this.receiptGrid.MasterTemplate).BeginInit();
        this.SuspendLayout();

        this.headingLabel.Name = "headingLabel";
        this.headingLabel.Text = "POS receipts";
        this.headingLabel.Location = new Point(20, 13);
        this.headingLabel.Size = new Size(878, 34);

        this.statusLabel.Name = "statusLabel";
        this.statusLabel.Text = "";
        this.statusLabel.Location = new Point(20, 584);
        this.statusLabel.Size = new Size(889, 39);
        this.headingLabel.Font = new Font("Segoe UI Semibold", 16F);

        this.searchBox.Name = "searchBox";
        this.searchBox.Location = new Point(20, 58);
        this.searchBox.Size = new Size(388, 26);

        this.refreshButton.Name = "refreshButton";
        this.refreshButton.Location = new Point(418, 56);
        this.refreshButton.Size = new Size(110, 29);
        this.refreshButton.Text = "Refresh";
        this.refreshButton.Click += this.RefreshClicked;

        this.receiptBox.Name = "receiptBox";
        this.receiptBox.Location = new Point(549, 98);
        this.receiptBox.Size = new Size(360, 436);

        this.exportButton.Name = "exportButton";
        this.exportButton.Location = new Point(20, 546);
        this.exportButton.Size = new Size(127, 29);
        this.exportButton.Text = "Save receipt";
        this.exportButton.Click += this.ExportClicked;

        this.printButton.Name = "printButton";
        this.printButton.Location = new Point(156, 546);
        this.printButton.Size = new Size(127, 29);
        this.printButton.Text = "Print receipt";
        this.printButton.Click += this.PrintClicked;

        this.copyButton.Name = "copyButton";
        this.copyButton.Location = new Point(293, 546);
        this.copyButton.Size = new Size(127, 29);
        this.copyButton.Text = "Copy receipt";
        this.copyButton.Click += this.CopyClicked;

        this.closeButton.Name = "closeButton";
        this.closeButton.Location = new Point(782, 546);
        this.closeButton.Size = new Size(127, 29);
        this.closeButton.Text = "Close";

        this.searchBox.AccessibleName = "Search invoice or receipt number";
        this.searchBox.NullText = "Search invoice or receipt number";
        this.searchBox.MaxLength = 120;
        this.receiptBox.Multiline = true;
        this.receiptBox.ReadOnly = true;
        this.receiptBox.ScrollBars = ScrollBars.Vertical;
        this.receiptBox.AccessibleName = "Selected receipt";
        this.exportButton.Enabled = false;
        this.printButton.Enabled = false;
        this.copyButton.Enabled = false;
        this.closeButton.DialogResult = DialogResult.Cancel;

        this.fileDialog.DefaultExt = "txt";
        this.fileDialog.Filter = "Text receipt (*.txt)|*.txt";
        this.fileDialog.Title = "Save receipt text";
        this.fileDialog.OverwritePrompt = true;
        this.fileDialog.RestoreDirectory = true;
        this.fileDialog.Title = "Save POS receipt";
        this.receiptDocument.DocumentName = "POS receipt";
        this.receiptDocument.BeginPrint += this.ReceiptBeginPrint;
        this.receiptDocument.PrintPage += this.ReceiptPrintPage;
        this.printDialog.Document = this.receiptDocument;
        this.printDialog.UseEXDialog = true;

        this.receiptGrid.Name = "receiptGrid";
        this.receiptGrid.Location = new Point(20, 98);
        this.receiptGrid.Size = new Size(508, 436);
        this.receiptGrid.ReadOnly = true;
        this.receiptGrid.MasterTemplate.AutoGenerateColumns = false;
        this.receiptGrid.MasterTemplate.AllowAddNewRow = false;
        this.receiptGrid.MasterTemplate.AllowDeleteRow = false;
        this.receiptGrid.SelectionChanged += this.ReceiptSelected;
        this.invoiceColumn.Name = "invoiceColumn";
        this.invoiceColumn.FieldName = "Invoice";
        this.invoiceColumn.HeaderText = "Invoice";
        this.invoiceColumn.Width = 125;
        this.customerColumn.Name = "customerColumn";
        this.customerColumn.FieldName = "Customer";
        this.customerColumn.HeaderText = "Customer";
        this.customerColumn.Width = 155;
        this.postedColumn.Name = "postedColumn";
        this.postedColumn.FieldName = "Committed";
        this.postedColumn.HeaderText = "Checked out";
        this.postedColumn.Width = 140;
        this.postedColumn.FormatString = "{0:g}";
        this.totalColumn.Name = "totalColumn";
        this.totalColumn.FieldName = "Total";
        this.totalColumn.HeaderText = "Total";
        this.totalColumn.Width = 100;
        this.totalColumn.FormatString = "{0:N2}";
        this.paidColumn.Name = "paidColumn";
        this.paidColumn.FieldName = "Paid";
        this.paidColumn.HeaderText = "Paid";
        this.paidColumn.Width = 100;
        this.paidColumn.FormatString = "{0:N2}";
        this.dueColumn.Name = "dueColumn";
        this.dueColumn.FieldName = "Outstanding";
        this.dueColumn.HeaderText = "Balance";
        this.dueColumn.Width = 100;
        this.dueColumn.FormatString = "{0:N2}";
        this.receiptGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] { this.invoiceColumn, this.customerColumn, this.postedColumn, this.totalColumn, this.paidColumn, this.dueColumn });

        this.Name = "PosReceiptHistoryForm";
        this.Text = "POS receipts";
        this.FormBorderStyle = FormBorderStyle.FixedDialog;
        this.MaximizeBox = false;
        this.MinimizeBox = false;
        this.ClientSize = new Size(930, 630);
        this.AutoScaleMode = AutoScaleMode.Font;
        this.AutoScaleDimensions = new SizeF(7F, 15F);
        this.StartPosition = FormStartPosition.CenterParent;
        this.CancelButton = this.closeButton;
        this.Controls.Add(this.headingLabel);
        this.Controls.Add(this.statusLabel);
        this.Controls.Add(this.searchBox);
        this.Controls.Add(this.refreshButton);
        this.Controls.Add(this.receiptBox);
        this.Controls.Add(this.exportButton);
        this.Controls.Add(this.printButton);
        this.Controls.Add(this.copyButton);
        this.Controls.Add(this.closeButton);
        this.Controls.Add(this.receiptGrid);
        this.Shown += this.ReceiptsShown;
        ((ISupportInitialize)this.receiptGrid.MasterTemplate).EndInit();
        ((ISupportInitialize)this.receiptGrid).EndInit();
        ((ISupportInitialize)this.searchBox).EndInit();
        ((ISupportInitialize)this.refreshButton).EndInit();
        ((ISupportInitialize)this.receiptBox).EndInit();
        ((ISupportInitialize)this.exportButton).EndInit();
        ((ISupportInitialize)this.printButton).EndInit();
        ((ISupportInitialize)this.copyButton).EndInit();
        ((ISupportInitialize)this.closeButton).EndInit();
        this.ResumeLayout(false);
    }

    private Label headingLabel;
    private Label statusLabel;
    private RadTextBox searchBox;
    private RadButton refreshButton;
    private RadTextBox receiptBox;
    private RadButton exportButton;
    private RadButton printButton;
    private RadButton copyButton;
    private RadButton closeButton;
    private RadGridView receiptGrid;
    private GridViewTextBoxColumn invoiceColumn;
    private GridViewTextBoxColumn customerColumn;
    private GridViewDateTimeColumn postedColumn;
    private GridViewDecimalColumn totalColumn;
    private GridViewDecimalColumn paidColumn;
    private GridViewDecimalColumn dueColumn;
    private SaveFileDialog fileDialog;
    private PrintDialog printDialog;
    private PrintDocument receiptDocument;
}
