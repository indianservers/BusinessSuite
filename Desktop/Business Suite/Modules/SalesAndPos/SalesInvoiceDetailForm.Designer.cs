using System.ComponentModel;
using Telerik.WinControls.UI;

namespace Business_Suite;

partial class SalesInvoiceDetailForm
{
    private void InitializeComponent()
    {
        this.headingLabel = new Label();
        this.summaryLabel = new Label();
        this.itemsGrid = new RadGridView();
        this.descriptionColumn = new GridViewTextBoxColumn();
        this.quantityColumn = new GridViewDecimalColumn();
        this.priceColumn = new GridViewDecimalColumn();
        this.discountColumn = new GridViewDecimalColumn();
        this.taxColumn = new GridViewDecimalColumn();
        this.totalColumn = new GridViewDecimalColumn();
        this.closeButton = new RadButton();
        this.approveButton = new RadButton();
        this.feedbackLabel = new Label();
        this.pdfButton = new RadButton();
        this.paymentButton = new RadButton();
        this.historyButton = new RadButton();
        this.cancelInvoiceButton = new RadButton();
        this.pdfDialog = new SaveFileDialog();
        ((ISupportInitialize)this.itemsGrid).BeginInit();
        ((ISupportInitialize)this.itemsGrid.MasterTemplate).BeginInit();
        ((ISupportInitialize)this.closeButton).BeginInit();
        ((ISupportInitialize)this.approveButton).BeginInit();
        ((ISupportInitialize)this.pdfButton).BeginInit();
        ((ISupportInitialize)this.paymentButton).BeginInit();
        ((ISupportInitialize)this.historyButton).BeginInit();
        ((ISupportInitialize)this.cancelInvoiceButton).BeginInit();
        this.SuspendLayout();

        this.headingLabel.Name = "headingLabel";
        this.headingLabel.Location = new Point(20, 15);
        this.headingLabel.Size = new Size(444, 36);
        this.headingLabel.Anchor = AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Top;

        this.historyButton.Name = "historyButton";
        this.historyButton.Text = "Payment history";
        this.historyButton.Location = new Point(647, 20);
        this.historyButton.Size = new Size(153, 30);
        this.historyButton.Anchor = AnchorStyles.Top | AnchorStyles.Right;
        this.historyButton.Click += this.HistoryClicked;

        this.cancelInvoiceButton.Name = "cancelInvoiceButton";
        this.cancelInvoiceButton.Text = "Cancel invoice";
        this.cancelInvoiceButton.Location = new Point(485, 20);
        this.cancelInvoiceButton.Size = new Size(152, 30);
        this.cancelInvoiceButton.Anchor = AnchorStyles.Top | AnchorStyles.Right;
        this.cancelInvoiceButton.Enabled = false;
        this.cancelInvoiceButton.Click += this.CancelInvoiceClicked;
        this.headingLabel.Font = new Font("Segoe UI Semibold", 20F);

        this.summaryLabel.Name = "summaryLabel";
        this.summaryLabel.Location = new Point(20, 60);
        this.summaryLabel.Size = new Size(780, 30);

        this.itemsGrid.Name = "itemsGrid";
        this.itemsGrid.Location = new Point(20, 98);
        this.itemsGrid.Size = new Size(780, 320);
        this.itemsGrid.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Bottom;
        this.itemsGrid.ReadOnly = true;
        this.itemsGrid.MasterTemplate.AutoGenerateColumns = false;
        this.itemsGrid.MasterTemplate.AllowAddNewRow = false;
        this.itemsGrid.MasterTemplate.AllowDeleteRow = false;
        this.itemsGrid.MasterTemplate.AutoSizeColumnsMode = GridViewAutoSizeColumnsMode.Fill;

        this.descriptionColumn.Name = "descriptionColumn";
        this.descriptionColumn.FieldName = "Description";
        this.descriptionColumn.HeaderText = "Description";
        this.descriptionColumn.Width = 280;
        this.quantityColumn.Name = "quantityColumn";
        this.quantityColumn.FieldName = "Quantity";
        this.quantityColumn.HeaderText = "Quantity";
        this.quantityColumn.FormatString = "{0:0.##########}";
        this.quantityColumn.Width = 95;
        this.priceColumn.Name = "priceColumn";
        this.priceColumn.FieldName = "UnitPrice";
        this.priceColumn.HeaderText = "Unit price";
        this.priceColumn.FormatString = "{0:N2}";
        this.priceColumn.Width = 95;
        this.discountColumn.Name = "discountColumn";
        this.discountColumn.FieldName = "Discount";
        this.discountColumn.HeaderText = "Discount";
        this.discountColumn.FormatString = "{0:N2}";
        this.discountColumn.Width = 95;
        this.taxColumn.Name = "taxColumn";
        this.taxColumn.FieldName = "Tax";
        this.taxColumn.HeaderText = "Tax";
        this.taxColumn.FormatString = "{0:N2}";
        this.taxColumn.Width = 95;
        this.totalColumn.Name = "totalColumn";
        this.totalColumn.FieldName = "Total";
        this.totalColumn.HeaderText = "Line total";
        this.totalColumn.FormatString = "{0:N2}";
        this.totalColumn.Width = 95;
        this.itemsGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] { this.descriptionColumn, this.quantityColumn,
            this.priceColumn, this.discountColumn, this.taxColumn, this.totalColumn });

        this.feedbackLabel.Name = "feedbackLabel";
        this.feedbackLabel.Anchor = AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Bottom;
        this.feedbackLabel.Location = new Point(20, 437);
        this.feedbackLabel.Size = new Size(222, 28);
        this.feedbackLabel.AutoEllipsis = true;

        this.paymentButton.Name = "paymentButton";
        this.paymentButton.Text = "Record payment";
        this.paymentButton.Location = new Point(251, 432);
        this.paymentButton.Size = new Size(147, 29);
        this.paymentButton.Anchor = AnchorStyles.Bottom | AnchorStyles.Right;
        this.paymentButton.Enabled = false;
        this.paymentButton.Click += this.PaymentClicked;

        this.pdfButton.Name = "pdfButton";
        this.pdfButton.Text = "Save invoice PDF";
        this.pdfButton.Location = new Point(408, 432);
        this.pdfButton.Size = new Size(126, 29);
        this.pdfButton.Anchor = AnchorStyles.Bottom | AnchorStyles.Right;
        this.pdfButton.Enabled = false;
        this.pdfButton.Click += this.PdfClicked;

        this.pdfDialog.Filter = "PDF documents (*.pdf)|*.pdf";
        this.pdfDialog.DefaultExt = "pdf";
        this.pdfDialog.Title = "Save invoice PDF";

        this.approveButton.Name = "approveButton";
        this.approveButton.Text = "Approve invoice";
        this.approveButton.Location = new Point(545, 432);
        this.approveButton.Size = new Size(139, 29);
        this.approveButton.Anchor = AnchorStyles.Bottom | AnchorStyles.Right;
        this.approveButton.Enabled = false;
        this.approveButton.Click += this.ApproveClicked;

        this.closeButton.Name = "closeButton";
        this.closeButton.Text = "Close";
        this.closeButton.Location = new Point(694, 432);
        this.closeButton.Size = new Size(106, 29);
        this.closeButton.Anchor = AnchorStyles.Bottom | AnchorStyles.Right;
        this.closeButton.DialogResult = DialogResult.Cancel;

        this.AutoScaleDimensions = new SizeF(7F, 15F);
        this.AutoScaleMode = AutoScaleMode.Font;
        this.ClientSize = new Size(820, 479);
        this.MinimumSize = new Size(650, 405);
        this.CancelButton = this.closeButton;
        this.Controls.Add(this.headingLabel);
        this.Controls.Add(this.summaryLabel);
        this.Controls.Add(this.itemsGrid);
        this.Controls.Add(this.closeButton);
        this.Controls.Add(this.approveButton);
        this.Controls.Add(this.pdfButton);
        this.Controls.Add(this.paymentButton);
        this.Controls.Add(this.historyButton);
        this.Controls.Add(this.cancelInvoiceButton);
        this.Controls.Add(this.feedbackLabel);
        this.StartPosition = FormStartPosition.CenterParent;
        this.Name = "SalesInvoiceDetailForm";
        this.Text = "Sales invoice";
        this.Shown += this.ViewerShown;
        ((ISupportInitialize)this.itemsGrid.MasterTemplate).EndInit();
        ((ISupportInitialize)this.itemsGrid).EndInit();
        ((ISupportInitialize)this.closeButton).EndInit();
        ((ISupportInitialize)this.approveButton).EndInit();
        ((ISupportInitialize)this.pdfButton).EndInit();
        ((ISupportInitialize)this.paymentButton).EndInit();
        ((ISupportInitialize)this.historyButton).EndInit();
        ((ISupportInitialize)this.cancelInvoiceButton).EndInit();
        this.ResumeLayout(false);
    }

    private Label headingLabel;
    private Label summaryLabel;
    private RadGridView itemsGrid;
    private GridViewTextBoxColumn descriptionColumn;
    private GridViewDecimalColumn quantityColumn;
    private GridViewDecimalColumn priceColumn;
    private GridViewDecimalColumn discountColumn;
    private GridViewDecimalColumn taxColumn;
    private GridViewDecimalColumn totalColumn;
    private RadButton closeButton;
    private RadButton approveButton;
    private Label feedbackLabel;
    private RadButton pdfButton;
    private RadButton paymentButton;
    private RadButton historyButton;
    private RadButton cancelInvoiceButton;
    private SaveFileDialog pdfDialog;
}
