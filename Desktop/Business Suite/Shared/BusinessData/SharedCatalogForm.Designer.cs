using Telerik.WinControls.UI;

namespace Business_Suite;

partial class SharedCatalogForm
{
    private void InitializeComponent()
    {
        headingLabel = new Label();
        searchBox = new RadTextBox();
        archivedCheckBox = new CheckBox();
        searchButton = new RadButton();
        categoriesButton = new RadButton();
        exportButton = new RadButton();
        lifecycleButton = new RadButton();
        newOfferingButton = new RadButton();
        importButton = new RadButton();
        editOfferingButton = new RadButton();
        confirmButton = new RadButton();
        cancelButton = new RadButton();
        lifecyclePrompt = new Label();
        exportDialog = new SaveFileDialog();
        statusLabel = new Label();
        catalogGrid = new RadGridView();
        var skuColumn = new GridViewTextBoxColumn();
        var nameColumn = new GridViewTextBoxColumn();
        var kindColumn = new GridViewTextBoxColumn();
        var categoryColumn = new GridViewTextBoxColumn();
        var unitColumn = new GridViewTextBoxColumn();
        var priceColumn = new GridViewDecimalColumn();
        var currencyColumn = new GridViewTextBoxColumn();
        var taxColumn = new GridViewDecimalColumn();
        ((System.ComponentModel.ISupportInitialize)searchBox).BeginInit();
        ((System.ComponentModel.ISupportInitialize)searchButton).BeginInit();
        ((System.ComponentModel.ISupportInitialize)categoriesButton).BeginInit();
        ((System.ComponentModel.ISupportInitialize)exportButton).BeginInit();
        ((System.ComponentModel.ISupportInitialize)lifecycleButton).BeginInit();
        ((System.ComponentModel.ISupportInitialize)confirmButton).BeginInit();
        ((System.ComponentModel.ISupportInitialize)cancelButton).BeginInit();
        ((System.ComponentModel.ISupportInitialize)catalogGrid).BeginInit();
        ((System.ComponentModel.ISupportInitialize)catalogGrid.MasterTemplate).BeginInit();
        SuspendLayout();

        headingLabel.AutoSize = true;
        headingLabel.Font = new Font("Segoe UI Semibold", 19F);
        headingLabel.Location = new Point(24, 21);
        headingLabel.Name = "headingLabel";
        headingLabel.Text = "Products and Services";

        searchBox.AccessibleName = "Search catalog";
        searchBox.NullText = "Search name, SKU or description";
        searchBox.Location = new Point(27, 76);
        searchBox.Name = "searchBox";
        searchBox.Size = new Size(243, 24);
        searchButton.Location = new Point(281, 74);
        searchButton.Name = "searchButton";
        searchButton.Size = new Size(93, 26);
        searchButton.Text = "Search";
        searchButton.Click += Reload;
        archivedCheckBox.AutoSize = true;
        archivedCheckBox.Location = new Point(386, 78);
        archivedCheckBox.Name = "archivedCheckBox";
        archivedCheckBox.Text = "Archived";
        archivedCheckBox.CheckedChanged += Reload;
        categoriesButton.Location = new Point(471, 74);
        categoriesButton.Name = "categoriesButton";
        categoriesButton.Size = new Size(120, 26);
        categoriesButton.Text = "Categories";
        categoriesButton.Click += categoriesButton_Click;
        exportButton.Location = new Point(601, 74);
        exportButton.Name = "exportButton";
        exportButton.Size = new Size(105, 26);
        exportButton.Text = "Export";
        exportButton.Enabled = false;
        exportButton.Click += ExportClicked;
        importButton.Location = new Point(716, 74);
        importButton.Name = "importButton";
        importButton.Size = new Size(111, 26);
        importButton.Text = "Import catalog";
        importButton.Enabled = false;
        importButton.Click += ImportClicked;
        exportDialog.FileName = "products-services";
        exportDialog.Filter = "JSON catalog (*.json)|*.json|CSV catalog (*.csv)|*.csv|Excel workbook (*.xlsx)|*.xlsx";
        exportDialog.Title = "Export active and archived products and services";
        exportDialog.OverwritePrompt = true;
        exportDialog.RestoreDirectory = true;
        lifecycleButton.Anchor = AnchorStyles.Top | AnchorStyles.Right;
        lifecycleButton.Location = new Point(854, 25);
        lifecycleButton.Name = "lifecycleButton";
        lifecycleButton.Size = new Size(112, 28);
        lifecycleButton.Text = "Archive";
        lifecycleButton.Enabled = false;
        lifecycleButton.Click += RequestLifecycle;
        newOfferingButton.Anchor = AnchorStyles.Top | AnchorStyles.Right;
        newOfferingButton.Location = new Point(609, 25);
        newOfferingButton.Name = "newOfferingButton";
        newOfferingButton.Size = new Size(112, 28);
        newOfferingButton.Text = "New offering";
        newOfferingButton.Enabled = false;
        newOfferingButton.Click += NewOffering;
        editOfferingButton.Anchor = AnchorStyles.Top | AnchorStyles.Right;
        editOfferingButton.Location = new Point(732, 25);
        editOfferingButton.Name = "editOfferingButton";
        editOfferingButton.Size = new Size(112, 28);
        editOfferingButton.Text = "Edit";
        editOfferingButton.Enabled = false;
        editOfferingButton.Click += EditOffering;
        lifecyclePrompt.Anchor = AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
        lifecyclePrompt.Location = new Point(27, 570);
        lifecyclePrompt.Name = "lifecyclePrompt";
        lifecyclePrompt.Size = new Size(650, 27);
        lifecyclePrompt.AutoEllipsis = true;
        lifecyclePrompt.Visible = false;
        confirmButton.Anchor = AnchorStyles.Bottom | AnchorStyles.Right;
        confirmButton.Location = new Point(699, 567);
        confirmButton.Name = "confirmButton";
        confirmButton.Size = new Size(135, 27);
        confirmButton.Visible = false;
        confirmButton.Click += ConfirmLifecycle;
        cancelButton.Anchor = AnchorStyles.Bottom | AnchorStyles.Right;
        cancelButton.Location = new Point(850, 567);
        cancelButton.Name = "cancelButton";
        cancelButton.Size = new Size(116, 27);
        cancelButton.Text = "Cancel";
        cancelButton.Visible = false;
        cancelButton.Click += CancelLifecycle;

        skuColumn.Name = "sku";
        skuColumn.FieldName = "sku";
        skuColumn.HeaderText = "SKU";
        skuColumn.Width = 125;

        nameColumn.Name = "item_name";
        nameColumn.FieldName = "item_name";
        nameColumn.HeaderText = "Name";
        nameColumn.Width = 190;

        kindColumn.Name = "kind";
        kindColumn.FieldName = "kind";
        kindColumn.HeaderText = "Type";
        kindColumn.Width = 101;

        categoryColumn.Name = "category";
        categoryColumn.FieldName = "category";
        categoryColumn.HeaderText = "Category or subcategory";
        categoryColumn.Width = 190;

        unitColumn.Name = "unit";
        unitColumn.FieldName = "unit";
        unitColumn.HeaderText = "Unit";
        unitColumn.Width = 70;

        priceColumn.Name = "price";
        priceColumn.FieldName = "price";
        priceColumn.HeaderText = "Price";
        priceColumn.Width = 92;
        priceColumn.FormatString = "{0:N2}";

        currencyColumn.Name = "currency";
        currencyColumn.FieldName = "currency";
        currencyColumn.HeaderText = "Currency";
        currencyColumn.Width = 70;

        taxColumn.Name = "tax";
        taxColumn.FieldName = "tax";
        taxColumn.HeaderText = "Tax %";
        taxColumn.Width = 66;
        taxColumn.FormatString = "{0:N2}";

        catalogGrid.Anchor = AnchorStyles.Top | AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
        catalogGrid.Location = new Point(27, 121);
        catalogGrid.Name = "catalogGrid";
        catalogGrid.Size = new Size(940, 435);
        catalogGrid.ReadOnly = true;
        catalogGrid.MasterTemplate.AllowAddNewRow = false;
        catalogGrid.MasterTemplate.AllowDeleteRow = false;
        catalogGrid.MasterTemplate.AutoGenerateColumns = false;
        catalogGrid.MasterTemplate.AutoSizeColumnsMode = GridViewAutoSizeColumnsMode.Fill;
        catalogGrid.MasterTemplate.EnableFiltering = true;
        catalogGrid.ShowGroupPanel = false;
        catalogGrid.SelectionChanged += CatalogSelectionChanged;
        catalogGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[]
        {
            skuColumn, nameColumn, kindColumn, categoryColumn, unitColumn, priceColumn, currencyColumn, taxColumn
        });

        statusLabel.Anchor = AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
        statusLabel.Location = new Point(27, 570);
        statusLabel.Name = "statusLabel";
        statusLabel.Size = new Size(940, 27);

        AcceptButton = searchButton;
        AutoScaleDimensions = new SizeF(7F, 15F);
        AutoScaleMode = AutoScaleMode.Font;
        BackColor = Color.FromArgb(242, 245, 251);
        ClientSize = new Size(994, 609);
        Controls.Add(headingLabel);
        Controls.Add(searchBox);
        Controls.Add(searchButton);
        Controls.Add(categoriesButton);
        Controls.Add(exportButton);
        Controls.Add(lifecycleButton);
        Controls.Add(newOfferingButton);
        Controls.Add(importButton);
        Controls.Add(editOfferingButton);
        Controls.Add(lifecyclePrompt);
        Controls.Add(confirmButton);
        Controls.Add(cancelButton);
        Controls.Add(archivedCheckBox);
        Controls.Add(catalogGrid);
        Controls.Add(statusLabel);
        Font = new Font("Segoe UI", 9F);
        MinimumSize = new Size(860, 480);
        Name = "SharedCatalogForm";
        StartPosition = FormStartPosition.CenterParent;
        Text = "Business Suite | Products and Services";
        Load += Reload;
        FormClosed += SharedCatalogForm_FormClosed;
        ((System.ComponentModel.ISupportInitialize)catalogGrid.MasterTemplate).EndInit();
        ((System.ComponentModel.ISupportInitialize)catalogGrid).EndInit();
        ((System.ComponentModel.ISupportInitialize)searchBox).EndInit();
        ((System.ComponentModel.ISupportInitialize)searchButton).EndInit();
        ((System.ComponentModel.ISupportInitialize)categoriesButton).EndInit();
        ((System.ComponentModel.ISupportInitialize)exportButton).EndInit();
        ((System.ComponentModel.ISupportInitialize)lifecycleButton).EndInit();
        ((System.ComponentModel.ISupportInitialize)confirmButton).EndInit();
        ((System.ComponentModel.ISupportInitialize)cancelButton).EndInit();
        ResumeLayout(false);
        PerformLayout();
    }

    private Label headingLabel;
    private RadTextBox searchBox;
    private RadButton searchButton;
    private RadButton categoriesButton;
    private RadButton exportButton;
    private RadButton lifecycleButton;
    private RadButton newOfferingButton;
    private RadButton importButton;
    private RadButton editOfferingButton;
    private RadButton confirmButton;
    private RadButton cancelButton;
    private Label lifecyclePrompt;
    private SaveFileDialog exportDialog;
    private CheckBox archivedCheckBox;
    private RadGridView catalogGrid;
    private Label statusLabel;
}
