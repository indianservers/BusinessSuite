using System.ComponentModel;
using Telerik.WinControls.UI;

namespace Business_Suite;

partial class PosReturnHistoryForm
{
    private void InitializeComponent()
    {
        this.headingLabel = new Label();
        this.summaryLabel = new Label();
        this.statusLabel = new Label();
        this.searchBox = new RadTextBox();
        this.refreshButton = new RadButton();
        this.closeButton = new RadButton();
        this.returnsGrid = new RadGridView();
        this.numberColumn = new GridViewTextBoxColumn();
        this.orderColumn = new GridViewTextBoxColumn();
        this.statusColumn = new GridViewTextBoxColumn();
        this.methodColumn = new GridViewTextBoxColumn();
        this.refundStateColumn = new GridViewTextBoxColumn();
        this.refundColumn = new GridViewDecimalColumn();
        this.createdColumn = new GridViewDateTimeColumn();
        this.detailsGrid = new RadGridView();
        this.productColumn = new GridViewTextBoxColumn();
        this.quantityColumn = new GridViewDecimalColumn();
        this.taxColumn = new GridViewDecimalColumn();
        this.amountColumn = new GridViewDecimalColumn();
        this.conditionColumn = new GridViewTextBoxColumn();
        this.restockColumn = new GridViewCheckBoxColumn();
        ((ISupportInitialize)this.searchBox).BeginInit();
        ((ISupportInitialize)this.refreshButton).BeginInit();
        ((ISupportInitialize)this.closeButton).BeginInit();
        ((ISupportInitialize)this.returnsGrid).BeginInit();
        ((ISupportInitialize)this.returnsGrid.MasterTemplate).BeginInit();
        ((ISupportInitialize)this.detailsGrid).BeginInit();
        ((ISupportInitialize)this.detailsGrid.MasterTemplate).BeginInit();
        this.SuspendLayout();

        this.headingLabel.Name = "headingLabel";
        this.headingLabel.Text = "POS return register";
        this.headingLabel.Location = new Point(20, 12);
        this.headingLabel.Size = new Size(905, 33);

        this.summaryLabel.Name = "summaryLabel";
        this.summaryLabel.Text = "Return details";
        this.summaryLabel.Location = new Point(20, 257);
        this.summaryLabel.Size = new Size(910, 28);

        this.statusLabel.Name = "statusLabel";
        this.statusLabel.Text = "";
        this.statusLabel.Location = new Point(20, 478);
        this.statusLabel.Size = new Size(788, 34);
        this.headingLabel.Font = new Font("Segoe UI Semibold", 16F);
        this.summaryLabel.AutoEllipsis = true;

        this.searchBox.Name = "searchBox";
        this.searchBox.Location = new Point(20, 55);
        this.searchBox.Size = new Size(423, 27);

        this.refreshButton.Name = "refreshButton";
        this.refreshButton.Location = new Point(455, 54);
        this.refreshButton.Size = new Size(107, 29);
        this.refreshButton.Text = "Refresh";
        this.refreshButton.Click += this.RefreshClicked;

        this.closeButton.Name = "closeButton";
        this.closeButton.Location = new Point(825, 480);
        this.closeButton.Size = new Size(107, 29);
        this.closeButton.Text = "Close";
        this.searchBox.AccessibleName = "Search return or original order";
        this.searchBox.NullText = "Search return or original order";
        this.searchBox.MaxLength = 120;
        this.closeButton.DialogResult = DialogResult.Cancel;


        this.returnsGrid.Name = "returnsGrid";
        this.returnsGrid.Location = new Point(20, 92);
        this.returnsGrid.Size = new Size(912, 151);
        this.returnsGrid.ReadOnly = true;
        this.returnsGrid.MasterTemplate.AutoGenerateColumns = false;
        this.returnsGrid.MasterTemplate.AllowAddNewRow = false;
        this.returnsGrid.MasterTemplate.AllowDeleteRow = false;
        this.returnsGrid.MasterTemplate.AutoSizeColumnsMode = GridViewAutoSizeColumnsMode.Fill;
        this.returnsGrid.SelectionChanged += this.ReturnSelected;
        this.numberColumn.Name = "numberColumn";
        this.numberColumn.FieldName = "Number";
        this.numberColumn.HeaderText = "Return #";
        this.numberColumn.Width = 105;
        this.orderColumn.Name = "orderColumn";
        this.orderColumn.FieldName = "Order";
        this.orderColumn.HeaderText = "Original order";
        this.orderColumn.Width = 120;
        this.statusColumn.Name = "statusColumn";
        this.statusColumn.FieldName = "State";
        this.statusColumn.HeaderText = "Status";
        this.statusColumn.Width = 105;
        this.methodColumn.Name = "methodColumn";
        this.methodColumn.FieldName = "RefundMethod";
        this.methodColumn.HeaderText = "Refund method";
        this.methodColumn.Width = 111;
        this.refundStateColumn.Name = "refundStateColumn";
        this.refundStateColumn.FieldName = "RefundStatus";
        this.refundStateColumn.HeaderText = "Refund status";
        this.refundStateColumn.Width = 111;
        this.refundColumn.Name = "refundColumn";
        this.refundColumn.FieldName = "Amount";
        this.refundColumn.HeaderText = "Refund amount";
        this.refundColumn.Width = 108;
        this.refundColumn.FormatString = "{0:N2}";
        this.createdColumn.Name = "createdColumn";
        this.createdColumn.FieldName = "Created";
        this.createdColumn.HeaderText = "Created";
        this.createdColumn.Width = 132;
        this.createdColumn.FormatString = "{0:g}";
        this.returnsGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] { this.numberColumn, this.orderColumn, this.statusColumn, this.methodColumn, this.refundStateColumn, this.refundColumn, this.createdColumn });

        this.detailsGrid.Name = "detailsGrid";
        this.detailsGrid.Location = new Point(20, 290);
        this.detailsGrid.Size = new Size(912, 175);
        this.detailsGrid.ReadOnly = true;
        this.detailsGrid.MasterTemplate.AutoGenerateColumns = false;
        this.detailsGrid.MasterTemplate.AllowAddNewRow = false;
        this.detailsGrid.MasterTemplate.AllowDeleteRow = false;
        this.detailsGrid.MasterTemplate.AutoSizeColumnsMode = GridViewAutoSizeColumnsMode.Fill;

        this.productColumn.Name = "productColumn";
        this.productColumn.FieldName = "Product";
        this.productColumn.HeaderText = "Product";
        this.productColumn.Width = 225;
        this.quantityColumn.Name = "quantityColumn";
        this.quantityColumn.FieldName = "Quantity";
        this.quantityColumn.HeaderText = "Quantity";
        this.quantityColumn.Width = 90;
        this.quantityColumn.FormatString = "{0:0.###}";
        this.taxColumn.Name = "taxColumn";
        this.taxColumn.FieldName = "Tax";
        this.taxColumn.HeaderText = "Tax";
        this.taxColumn.Width = 95;
        this.taxColumn.FormatString = "{0:N2}";
        this.amountColumn.Name = "amountColumn";
        this.amountColumn.FieldName = "Amount";
        this.amountColumn.HeaderText = "Refund amount";
        this.amountColumn.Width = 105;
        this.amountColumn.FormatString = "{0:N2}";
        this.conditionColumn.Name = "conditionColumn";
        this.conditionColumn.FieldName = "Condition";
        this.conditionColumn.HeaderText = "Condition";
        this.conditionColumn.Width = 142;
        this.restockColumn.Name = "restockColumn";
        this.restockColumn.FieldName = "Restock";
        this.restockColumn.HeaderText = "Restocked";
        this.restockColumn.Width = 80;
        this.detailsGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] { this.productColumn, this.quantityColumn, this.taxColumn, this.amountColumn, this.conditionColumn, this.restockColumn });

        this.Name = "PosReturnHistoryForm";
        this.Text = "POS return register";
        this.FormBorderStyle = FormBorderStyle.FixedDialog;
        this.MaximizeBox = false;
        this.MinimizeBox = false;
        this.ClientSize = new Size(952, 528);
        this.AutoScaleMode = AutoScaleMode.Font;
        this.AutoScaleDimensions = new SizeF(7F, 15F);
        this.StartPosition = FormStartPosition.CenterParent;
        this.CancelButton = this.closeButton;
        this.Controls.Add(this.headingLabel);
        this.Controls.Add(this.summaryLabel);
        this.Controls.Add(this.statusLabel);
        this.Controls.Add(this.searchBox);
        this.Controls.Add(this.refreshButton);
        this.Controls.Add(this.closeButton);
        this.Controls.Add(this.returnsGrid);
        this.Controls.Add(this.detailsGrid);
        this.Shown += this.HistoryShown;
        ((ISupportInitialize)this.returnsGrid.MasterTemplate).EndInit();
        ((ISupportInitialize)this.returnsGrid).EndInit();
        ((ISupportInitialize)this.detailsGrid.MasterTemplate).EndInit();
        ((ISupportInitialize)this.detailsGrid).EndInit();
        ((ISupportInitialize)this.searchBox).EndInit();
        ((ISupportInitialize)this.refreshButton).EndInit();
        ((ISupportInitialize)this.closeButton).EndInit();
        this.ResumeLayout(false);
    }

    private Label headingLabel;
    private Label summaryLabel;
    private Label statusLabel;
    private RadTextBox searchBox;
    private RadButton refreshButton;
    private RadButton closeButton;
    private RadGridView returnsGrid;
    private GridViewTextBoxColumn numberColumn;
    private GridViewTextBoxColumn orderColumn;
    private GridViewTextBoxColumn statusColumn;
    private GridViewTextBoxColumn methodColumn;
    private GridViewTextBoxColumn refundStateColumn;
    private GridViewDecimalColumn refundColumn;
    private GridViewDateTimeColumn createdColumn;
    private RadGridView detailsGrid;
    private GridViewTextBoxColumn productColumn;
    private GridViewDecimalColumn quantityColumn;
    private GridViewDecimalColumn taxColumn;
    private GridViewDecimalColumn amountColumn;
    private GridViewTextBoxColumn conditionColumn;
    private GridViewCheckBoxColumn restockColumn;
}
