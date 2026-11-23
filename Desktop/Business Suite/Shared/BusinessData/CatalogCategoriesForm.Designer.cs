using Telerik.WinControls.UI;

namespace Business_Suite;

partial class CatalogCategoriesForm
{
    private void InitializeComponent()
    {
        categoryGrid = new RadGridView();
        heading = new Label();
        nameLabel = new Label();
        nameBox = new RadTextBox();
        statusLabel = new Label();
        newCategoryButton = new RadButton();
        newSubcategoryButton = new RadButton();
        renameButton = new RadButton();
        removeButton = new RadButton();
        loadButton = new RadButton();
        saveButton = new RadButton();
        var nameColumn = new GridViewTextBoxColumn();
        var parentColumn = new GridViewTextBoxColumn();
        ((System.ComponentModel.ISupportInitialize)categoryGrid).BeginInit();
        ((System.ComponentModel.ISupportInitialize)categoryGrid.MasterTemplate).BeginInit();
        ((System.ComponentModel.ISupportInitialize)nameBox).BeginInit();
        ((System.ComponentModel.ISupportInitialize)newCategoryButton).BeginInit();
        ((System.ComponentModel.ISupportInitialize)newSubcategoryButton).BeginInit();
        ((System.ComponentModel.ISupportInitialize)renameButton).BeginInit();
        ((System.ComponentModel.ISupportInitialize)removeButton).BeginInit();
        ((System.ComponentModel.ISupportInitialize)loadButton).BeginInit();
        ((System.ComponentModel.ISupportInitialize)saveButton).BeginInit();
        SuspendLayout();

        heading.AutoSize = true;
        heading.Font = new Font("Segoe UI Semibold", 19F);
        heading.Location = new Point(24, 18);
        heading.Name = "heading";
        heading.Text = "Categories and subcategories";
        nameLabel.AutoSize = true;
        nameLabel.Location = new Point(25, 66);
        nameLabel.Name = "nameLabel";
        nameLabel.Text = "Name";
        nameBox.AccessibleName = "Category or subcategory name";
        nameBox.Enabled = false;
        nameBox.Location = new Point(25, 86);
        nameBox.Name = "nameBox";
        nameBox.Size = new Size(405, 25);
        nameBox.MaxLength = 120;
        nameBox.TextChanged += nameBox_TextChanged;

        newCategoryButton.Enabled = false;
        newCategoryButton.Location = new Point(25, 125);
        newCategoryButton.Name = "newCategoryButton";
        newCategoryButton.Size = new Size(110, 31);
        newCategoryButton.Text = "New category";
        newCategoryButton.Click += newCategory_Click;

        newSubcategoryButton.Enabled = false;
        newSubcategoryButton.Location = new Point(145, 125);
        newSubcategoryButton.Name = "newSubcategoryButton";
        newSubcategoryButton.Size = new Size(135, 31);
        newSubcategoryButton.Text = "New subcategory";
        newSubcategoryButton.Click += newSubcategory_Click;

        renameButton.Enabled = false;
        renameButton.Location = new Point(290, 125);
        renameButton.Name = "renameButton";
        renameButton.Size = new Size(86, 31);
        renameButton.Text = "Rename";
        renameButton.Click += rename_Click;

        removeButton.Enabled = false;
        removeButton.Location = new Point(386, 125);
        removeButton.Name = "removeButton";
        removeButton.Size = new Size(86, 31);
        removeButton.Text = "Remove";
        removeButton.Click += remove_Click;

        loadButton.Enabled = true;
        loadButton.Location = new Point(482, 125);
        loadButton.Name = "loadButton";
        loadButton.Size = new Size(86, 31);
        loadButton.Text = "Reload";
        loadButton.Click += load_Click;

        saveButton.Enabled = false;
        saveButton.Location = new Point(578, 125);
        saveButton.Name = "saveButton";
        saveButton.Size = new Size(86, 31);
        saveButton.Text = "Save";
        saveButton.Click += save_Click;

        nameColumn.Name = "Name";
        nameColumn.FieldName = "Name";
        nameColumn.HeaderText = "Name";
        nameColumn.Width = 360;
        parentColumn.Name = "Parent";
        parentColumn.FieldName = "Parent";
        parentColumn.HeaderText = "Parent category";
        parentColumn.Width = 270;

        categoryGrid.Anchor = AnchorStyles.Top | AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
        categoryGrid.Enabled = false;
        categoryGrid.Location = new Point(25, 173);
        categoryGrid.Name = "categoryGrid";
        categoryGrid.Size = new Size(639, 330);
        categoryGrid.ReadOnly = true;
        categoryGrid.ShowGroupPanel = false;
        categoryGrid.MasterTemplate.AllowAddNewRow = false;
        categoryGrid.MasterTemplate.AllowDeleteRow = false;
        categoryGrid.MasterTemplate.AutoGenerateColumns = false;
        categoryGrid.MasterTemplate.AutoSizeColumnsMode = GridViewAutoSizeColumnsMode.Fill;
        categoryGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] { nameColumn, parentColumn });
        categoryGrid.CurrentRowChanged += categoryGrid_CurrentRowChanged;

        statusLabel.Anchor = AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
        statusLabel.Location = new Point(25, 518);
        statusLabel.Name = "statusLabel";
        statusLabel.Size = new Size(639, 38);

        AutoScaleDimensions = new SizeF(7F, 15F);
        AutoScaleMode = AutoScaleMode.Font;
        BackColor = Color.FromArgb(242, 245, 251);
        ClientSize = new Size(689, 566);
        Controls.Add(heading);
        Controls.Add(nameLabel);
        Controls.Add(nameBox);
        Controls.Add(newCategoryButton);
        Controls.Add(newSubcategoryButton);
        Controls.Add(renameButton);
        Controls.Add(removeButton);
        Controls.Add(loadButton);
        Controls.Add(saveButton);
        Controls.Add(categoryGrid);
        Controls.Add(statusLabel);
        Font = new Font("Segoe UI", 9F);
        MinimumSize = new Size(705, 430);
        Name = "CatalogCategoriesForm";
        StartPosition = FormStartPosition.CenterParent;
        Text = "Business Suite | Catalog categories";
        Load += load_Click;
        FormClosing += CatalogCategoriesForm_FormClosing;
        ((System.ComponentModel.ISupportInitialize)categoryGrid.MasterTemplate).EndInit();
        ((System.ComponentModel.ISupportInitialize)categoryGrid).EndInit();
        ((System.ComponentModel.ISupportInitialize)nameBox).EndInit();
        ((System.ComponentModel.ISupportInitialize)newCategoryButton).EndInit();
        ((System.ComponentModel.ISupportInitialize)newSubcategoryButton).EndInit();
        ((System.ComponentModel.ISupportInitialize)renameButton).EndInit();
        ((System.ComponentModel.ISupportInitialize)removeButton).EndInit();
        ((System.ComponentModel.ISupportInitialize)loadButton).EndInit();
        ((System.ComponentModel.ISupportInitialize)saveButton).EndInit();
        ResumeLayout(false);
        PerformLayout();
    }

    private RadGridView categoryGrid;
    private Label heading;
    private Label nameLabel;
    private RadTextBox nameBox;
    private Label statusLabel;
    private RadButton newCategoryButton;
    private RadButton newSubcategoryButton;
    private RadButton renameButton;
    private RadButton removeButton;
    private RadButton loadButton;
    private RadButton saveButton;
}
