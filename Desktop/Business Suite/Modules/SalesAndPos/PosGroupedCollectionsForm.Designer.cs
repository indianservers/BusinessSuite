using System.ComponentModel;
using Telerik.WinControls;
using Telerik.WinControls.UI;

namespace Business_Suite;

partial class PosGroupedCollectionsForm
{
    private void InitializeComponent()
    {
        this.headingLabel = new Label();
        this.amountLabel = new Label();
        this.methodLabel = new Label();
        this.referenceLabel = new Label();
        this.statusLabel = new Label();
        this.searchBox = new RadTextBox();
        this.refreshButton = new RadButton();
        this.amountEditor = new RadSpinEditor();
        this.methodPicker = new RadDropDownList();
        this.referenceBox = new RadTextBox();
        this.recordButton = new RadButton();
        this.closeButton = new RadButton();
        this.invoiceGrid = new RadGridView();
        this.invoiceColumn = new GridViewTextBoxColumn();
        this.customerColumn = new GridViewTextBoxColumn();
        this.currencyColumn = new GridViewTextBoxColumn();
        this.totalColumn = new GridViewDecimalColumn();
        this.paidColumn = new GridViewDecimalColumn();
        this.outstandingColumn = new GridViewDecimalColumn();
        ((ISupportInitialize)this.searchBox).BeginInit();
        ((ISupportInitialize)this.refreshButton).BeginInit();
        ((ISupportInitialize)this.amountEditor).BeginInit();
        ((ISupportInitialize)this.methodPicker).BeginInit();
        ((ISupportInitialize)this.referenceBox).BeginInit();
        ((ISupportInitialize)this.recordButton).BeginInit();
        ((ISupportInitialize)this.closeButton).BeginInit();
        ((ISupportInitialize)this.invoiceGrid).BeginInit();
        ((ISupportInitialize)this.invoiceGrid.MasterTemplate).BeginInit();
        this.SuspendLayout();

        this.headingLabel.Name = "headingLabel";
        this.headingLabel.Text = "POS invoice payments";
        this.headingLabel.Location = new Point(20, 12);
        this.headingLabel.Size = new Size(875, 31);

        this.amountLabel.Name = "amountLabel";
        this.amountLabel.Text = "Amount received";
        this.amountLabel.Location = new Point(20, 355);
        this.amountLabel.Size = new Size(131, 22);

        this.methodLabel.Name = "methodLabel";
        this.methodLabel.Text = "Payment method";
        this.methodLabel.Location = new Point(164, 355);
        this.methodLabel.Size = new Size(156, 22);

        this.referenceLabel.Name = "referenceLabel";
        this.referenceLabel.Text = "Payment reference";
        this.referenceLabel.Location = new Point(333, 355);
        this.referenceLabel.Size = new Size(285, 22);

        this.statusLabel.Name = "statusLabel";
        this.statusLabel.Text = "";
        this.statusLabel.Location = new Point(20, 421);
        this.statusLabel.Size = new Size(879, 45);
        this.headingLabel.Font = new Font("Segoe UI Semibold", 16F);

        this.searchBox.Name = "searchBox";
        this.searchBox.Location = new Point(20, 62);
        this.searchBox.Size = new Size(430, 27);

        this.refreshButton.Name = "refreshButton";
        this.refreshButton.Location = new Point(461, 61);
        this.refreshButton.Size = new Size(106, 27);
        this.refreshButton.Text = "Refresh";
        this.refreshButton.Click += this.RefreshClicked;

        this.amountEditor.Name = "amountEditor";
        this.amountEditor.Location = new Point(20, 380);
        this.amountEditor.Size = new Size(131, 27);

        this.methodPicker.Name = "methodPicker";
        this.methodPicker.Location = new Point(164, 380);
        this.methodPicker.Size = new Size(156, 27);

        this.referenceBox.Name = "referenceBox";
        this.referenceBox.Location = new Point(333, 380);
        this.referenceBox.Size = new Size(285, 27);

        this.recordButton.Name = "recordButton";
        this.recordButton.Location = new Point(630, 380);
        this.recordButton.Size = new Size(161, 28);
        this.recordButton.Text = "Record payment";
        this.recordButton.Click += this.RecordClicked;

        this.closeButton.Name = "closeButton";
        this.closeButton.Location = new Point(803, 380);
        this.closeButton.Size = new Size(99, 28);
        this.closeButton.Text = "Close";

        this.searchBox.AccessibleName = "Search invoice or customer";
        this.searchBox.NullText = "Search invoice or customer";
        this.searchBox.MaxLength = 120;
        this.amountEditor.DecimalPlaces = 2;
        this.amountEditor.Maximum = 99999999999M;
        this.amountEditor.Increment = 0.01M;
        this.amountEditor.AccessibleName = "Amount received";
        this.methodPicker.AccessibleName = "Payment method";
        this.methodPicker.DropDownStyle = RadDropDownStyle.DropDownList;
        this.referenceBox.AccessibleName = "Payment reference";
        this.referenceBox.MaxLength = 120;
        this.recordButton.Enabled = false;
        this.closeButton.DialogResult = DialogResult.Cancel;

        this.invoiceGrid.Name = "invoiceGrid";
        this.invoiceGrid.Location = new Point(20, 101);
        this.invoiceGrid.Size = new Size(882, 242);
        this.invoiceGrid.ReadOnly = true;
        this.invoiceGrid.MasterTemplate.AutoGenerateColumns = false;
        this.invoiceGrid.MasterTemplate.AllowAddNewRow = false;
        this.invoiceGrid.MasterTemplate.AllowDeleteRow = false;
        this.invoiceGrid.MasterTemplate.AutoSizeColumnsMode = GridViewAutoSizeColumnsMode.Fill;
        this.invoiceGrid.SelectionChanged += this.InvoiceSelectionChanged;
        this.invoiceColumn.Name = "invoiceColumn";
        this.invoiceColumn.FieldName = "Invoice";
        this.invoiceColumn.HeaderText = "Invoice";
        this.invoiceColumn.Width = 140;
        this.customerColumn.Name = "customerColumn";
        this.customerColumn.FieldName = "Customer";
        this.customerColumn.HeaderText = "Customer";
        this.customerColumn.Width = 230;
        this.currencyColumn.Name = "currencyColumn";
        this.currencyColumn.FieldName = "Currency";
        this.currencyColumn.HeaderText = "Currency";
        this.currencyColumn.Width = 100;
        this.totalColumn.Name = "totalColumn";
        this.totalColumn.FieldName = "Total";
        this.totalColumn.HeaderText = "Total";
        this.totalColumn.Width = 115;
        this.totalColumn.FormatString = "{0:N2}";
        this.paidColumn.Name = "paidColumn";
        this.paidColumn.FieldName = "Paid";
        this.paidColumn.HeaderText = "Paid";
        this.paidColumn.Width = 115;
        this.paidColumn.FormatString = "{0:N2}";
        this.outstandingColumn.Name = "outstandingColumn";
        this.outstandingColumn.FieldName = "Outstanding";
        this.outstandingColumn.HeaderText = "Outstanding";
        this.outstandingColumn.Width = 120;
        this.outstandingColumn.FormatString = "{0:N2}";
        this.invoiceGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] { this.invoiceColumn, this.customerColumn, this.currencyColumn, this.totalColumn, this.paidColumn, this.outstandingColumn });

        this.Name = "PosGroupedCollectionsForm";
        this.Text = "POS invoice payments";
        this.FormBorderStyle = FormBorderStyle.FixedDialog;
        this.MaximizeBox = false;
        this.MinimizeBox = false;
        this.ClientSize = new Size(922, 472);
        this.AutoScaleMode = AutoScaleMode.Font;
        this.AutoScaleDimensions = new SizeF(7F, 15F);
        this.StartPosition = FormStartPosition.CenterParent;
        this.CancelButton = this.closeButton;
        this.Controls.Add(this.headingLabel);
        this.Controls.Add(this.amountLabel);
        this.Controls.Add(this.methodLabel);
        this.Controls.Add(this.referenceLabel);
        this.Controls.Add(this.statusLabel);
        this.Controls.Add(this.searchBox);
        this.Controls.Add(this.refreshButton);
        this.Controls.Add(this.amountEditor);
        this.Controls.Add(this.methodPicker);
        this.Controls.Add(this.referenceBox);
        this.Controls.Add(this.recordButton);
        this.Controls.Add(this.closeButton);
        this.Controls.Add(this.invoiceGrid);
        this.Shown += this.CollectionsShown;
        this.FormClosing += this.CollectionsClosing;
        this.FormClosed += this.CollectionsClosed;
        ((ISupportInitialize)this.invoiceGrid.MasterTemplate).EndInit();
        ((ISupportInitialize)this.invoiceGrid).EndInit();
        ((ISupportInitialize)this.searchBox).EndInit();
        ((ISupportInitialize)this.refreshButton).EndInit();
        ((ISupportInitialize)this.amountEditor).EndInit();
        ((ISupportInitialize)this.methodPicker).EndInit();
        ((ISupportInitialize)this.referenceBox).EndInit();
        ((ISupportInitialize)this.recordButton).EndInit();
        ((ISupportInitialize)this.closeButton).EndInit();
        this.ResumeLayout(false);
    }

    private Label headingLabel;
    private Label amountLabel;
    private Label methodLabel;
    private Label referenceLabel;
    private Label statusLabel;
    private RadTextBox searchBox;
    private RadButton refreshButton;
    private RadSpinEditor amountEditor;
    private RadDropDownList methodPicker;
    private RadTextBox referenceBox;
    private RadButton recordButton;
    private RadButton closeButton;
    private RadGridView invoiceGrid;
    private GridViewTextBoxColumn invoiceColumn;
    private GridViewTextBoxColumn customerColumn;
    private GridViewTextBoxColumn currencyColumn;
    private GridViewDecimalColumn totalColumn;
    private GridViewDecimalColumn paidColumn;
    private GridViewDecimalColumn outstandingColumn;
}
