using Telerik.WinControls.UI;

namespace Business_Suite;

partial class CatalogImportForm
{
    private void InitializeComponent()
    {
        SuspendLayout();
        browseButton = new RadButton { Name = "browseButton", Text = "Choose catalog file", Location = new Point(20, 20),
            Size = new Size(164, 28) };
        browseButton.Click += BrowseClicked;
        fileLabel = new Label { Name = "fileLabel", Text = "No file selected", Location = new Point(198, 25),
            Size = new Size(599, 23), AutoEllipsis = true };
        grid = new RadGridView { Name = "grid", Location = new Point(20, 64), Size = new Size(785, 315), ReadOnly = true,
            AccessibleName = "Catalog import preview", ShowGroupPanel = false };
        grid.MasterTemplate.AutoGenerateColumns = false;
        grid.MasterTemplate.AllowAddNewRow = false;
        grid.MasterTemplate.AllowDeleteRow = false;
        grid.MasterTemplate.AutoSizeColumnsMode = GridViewAutoSizeColumnsMode.Fill;
        grid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] {
            new GridViewTextBoxColumn { Name = "kindColumn", FieldName = "Kind", HeaderText = "Type", Width = 85 },
            new GridViewTextBoxColumn { Name = "nameColumn", FieldName = "Name", HeaderText = "Name", Width = 245 },
            new GridViewTextBoxColumn { Name = "codeColumn", FieldName = "Code", HeaderText = "Code", Width = 155 },
            new GridViewDecimalColumn { Name = "priceColumn", FieldName = "Price", HeaderText = "Price", Width = 100 },
            new GridViewTextBoxColumn { Name = "currencyColumn", FieldName = "Currency", HeaderText = "Currency", Width = 75 },
            new GridViewTextBoxColumn { Name = "statusColumn", FieldName = "Status", HeaderText = "Status", Width = 85 }
        });
        feedback = new Label { Name = "feedback", Text = "Select a UTF-8 file with up to 500 offerings (2 MB).",
            Location = new Point(20, 392), Size = new Size(785, 40) };
        importButton = new RadButton { Name = "importButton", Text = "Import offerings", Location = new Point(514, 441),
            Size = new Size(145, 29), Enabled = false };
        importButton.Click += ImportClicked;
        closeButton = new RadButton { Name = "closeButton", Text = "Cancel", Location = new Point(669, 441),
            Size = new Size(136, 29), DialogResult = DialogResult.Cancel };
        picker = new OpenFileDialog { Filter = "Catalog files (*.xlsx;*.json;*.csv;*.tsv)|*.xlsx;*.json;*.csv;*.tsv", Title = "Choose a catalog import file",
            CheckFileExists = true, Multiselect = false };
        Controls.AddRange(new Control[] { browseButton, fileLabel, grid, feedback, importButton, closeButton });
        CancelButton = closeButton;
        ClientSize = new Size(825, 486);
        Font = new Font("Segoe UI", 9F);
        AutoScaleDimensions = new SizeF(7F, 15F);
        AutoScaleMode = AutoScaleMode.Font;
        StartPosition = FormStartPosition.CenterParent;
        FormBorderStyle = FormBorderStyle.FixedDialog;
        ShowInTaskbar = MaximizeBox = MinimizeBox = false;
        Name = "CatalogImportForm";
        Text = "Import products and services";
        FormClosing += ClosingImport;
        FormClosed += (_, _) => picker.Dispose();
        ResumeLayout(false);
        PerformLayout();
    }

    private Label fileLabel, feedback;
    private RadGridView grid;
    private RadButton browseButton, importButton, closeButton;
    private OpenFileDialog picker;
}
