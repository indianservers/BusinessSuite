using Telerik.WinControls.UI;

namespace Business_Suite;

partial class CatalogColumnMappingForm
{
    private void InitializeComponent()
    {
        SuspendLayout();
        instructions = new Label { Name = "instructions", Text = "Match file columns to catalog fields. Choose Skip column to leave a column out.",
            Location = new Point(20, 18), Size = new Size(720, 26) };
        worksheetPanel = new Panel { Name = "worksheetPanel", Location = new Point(20, 50), Size = new Size(725, 37), Visible = false };
        sheetLabel = new Label { Name = "sheetLabel", Text = "Worksheet", Location = new Point(0, 6), Size = new Size(85, 23) };
        sheetBox = new ComboBox { Name = "sheetBox", Location = new Point(90, 3), Size = new Size(252, 26),
            AccessibleName = "Worksheet", DropDownStyle = ComboBoxStyle.DropDownList };
        sheetBox.SelectedIndexChanged += SheetSelectionChanged;
        headerLabel = new Label { Name = "headerLabel", Text = "Header row", Location = new Point(362, 6), Size = new Size(84, 23) };
        headerBox = new NumericUpDown { Name = "headerBox", Location = new Point(450, 3), Size = new Size(75, 26),
            AccessibleName = "Header row", Minimum = 1, Maximum = 50, Value = 1 };
        headerBox.ValueChanged += SheetSelectionChanged;
        loadSheetButton = new RadButton { Name = "loadSheetButton", Text = "Load worksheet", Location = new Point(551, 2), Size = new Size(174, 29) };
        loadSheetButton.Click += LoadSheetClicked;
        worksheetPanel.Controls.AddRange(new Control[] { sheetLabel, sheetBox, headerLabel, headerBox, loadSheetButton });
        mappingGrid = new RadGridView { Name = "mappingGrid", Location = new Point(20, 93), Size = new Size(725, 264),
            AccessibleName = "Catalog column mapping", ShowGroupPanel = false };
        mappingGrid.MasterTemplate.AutoGenerateColumns = false;
        mappingGrid.MasterTemplate.AllowAddNewRow = false;
        mappingGrid.MasterTemplate.AllowDeleteRow = false;
        mappingGrid.MasterTemplate.AllowColumnReorder = false;
        mappingGrid.MasterTemplate.AutoSizeColumnsMode = GridViewAutoSizeColumnsMode.Fill;
        sourceColumn = new GridViewTextBoxColumn { Name = "sourceColumn", FieldName = "Source", HeaderText = "Column heading", Width = 210, ReadOnly = true };
        sampleColumn = new GridViewTextBoxColumn { Name = "sampleColumn", FieldName = "Sample", HeaderText = "First row", Width = 245, ReadOnly = true };
        destinationColumn = new GridViewComboBoxColumn { Name = "destinationColumn", FieldName = "Field",
            HeaderText = "Catalog field", DisplayMember = "Label", ValueMember = "Key", Width = 245 };
        mappingGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] { sourceColumn, sampleColumn, destinationColumn });
        typeLabel = new Label { Name = "typeLabel", Text = "Default type when unmapped", Location = new Point(20, 375), Size = new Size(232, 24) };
        defaultType = new RadDropDownList { Name = "defaultType", Location = new Point(255, 371), Size = new Size(143, 28),
            AccessibleName = "Default offering type", DropDownStyle = Telerik.WinControls.RadDropDownStyle.DropDownList };
        defaultType.Items.Add(new RadListDataItem("Product"));
        defaultType.Items.Add(new RadListDataItem("Service"));
        feedback = new Label { Name = "feedback", Location = new Point(20, 409), Size = new Size(725, 40),
            Text = "Name and SKU / Code are required." };
        mappingGrid.CellValueChanged += MappingChanged;
        defaultType.SelectedIndexChanged += MappingChanged;
        previewButton = new RadButton { Name = "previewButton", Text = "Preview offerings", Location = new Point(455, 451),
            Size = new Size(148, 29), Enabled = false };
        previewButton.Click += PreviewClicked;
        cancelButton = new RadButton { Name = "cancelButton", Text = "Cancel", Location = new Point(615, 451), Size = new Size(130, 29),
            DialogResult = DialogResult.Cancel };
        Controls.AddRange(new Control[] { instructions, worksheetPanel, mappingGrid, typeLabel, defaultType, feedback, previewButton, cancelButton });
        CancelButton = cancelButton;
        AutoScaleMode = AutoScaleMode.Font;
        AutoScaleDimensions = new SizeF(7F, 15F);
        Font = new Font("Segoe UI", 9F);
        ClientSize = new Size(765, 498);
        FormBorderStyle = FormBorderStyle.FixedDialog;
        ShowInTaskbar = MinimizeBox = MaximizeBox = false;
        StartPosition = FormStartPosition.CenterParent;
        Name = "CatalogColumnMappingForm";
        Text = "Match catalog columns";
        ResumeLayout(false);
        PerformLayout();
    }

    private Label instructions, typeLabel, feedback;
    private RadGridView mappingGrid;
    private GridViewTextBoxColumn sourceColumn, sampleColumn;
    private GridViewComboBoxColumn destinationColumn;
    private RadDropDownList defaultType;
    private RadButton previewButton, cancelButton;
    private Panel worksheetPanel;
    private Label sheetLabel, headerLabel;
    private ComboBox sheetBox;
    private NumericUpDown headerBox;
    private RadButton loadSheetButton;
}
