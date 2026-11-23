#nullable disable
using System.ComponentModel;
using System.Drawing;
using System.Windows.Forms;
using Telerik.WinControls.UI;

namespace Business_Suite;

partial class DocumentsAndCommunicationForm
{
    private void InitializeComponent()
    {
        this.titleLabel = new Label();
        this.providerLabel = new Label();
        this.searchBox = new RadTextBox();
        this.disabledCheck = new CheckBox();
        this.favoritesOnlyCheck = new CheckBox();
        this.favoriteButton = new RadButton();
        this.refreshButton = new RadButton();
        this.newButton = new RadButton();
        this.openButton = new RadButton();
        this.disableButton = new RadButton();
        this.historyButton = new RadButton();
        this.composeButton = new RadButton();
        this.draftsButton = new RadButton();
        this.deliveryButton = new RadButton();
        this.customersButton = new RadButton();
        this.campaignsButton = new RadButton();
        this.autoResponsesButton = new RadButton();
        this.webformsButton = new RadButton();
        this.statusLabel = new Label();
        this.templateGrid = new RadGridView();
        this.nameColumn = new GridViewTextBoxColumn();
        this.subjectColumn = new GridViewTextBoxColumn();
        this.moduleColumn = new GridViewTextBoxColumn();
        this.activeColumn = new GridViewCheckBoxColumn();
        this.favoriteColumn = new GridViewCheckBoxColumn();
        this.updatedColumn = new GridViewTextBoxColumn();
        ((ISupportInitialize)this.searchBox).BeginInit();
        ((ISupportInitialize)this.refreshButton).BeginInit();
        ((ISupportInitialize)this.newButton).BeginInit();
        ((ISupportInitialize)this.openButton).BeginInit();
        ((ISupportInitialize)this.disableButton).BeginInit();
        ((ISupportInitialize)this.historyButton).BeginInit();
        ((ISupportInitialize)this.composeButton).BeginInit();
        ((ISupportInitialize)this.draftsButton).BeginInit();
        ((ISupportInitialize)this.deliveryButton).BeginInit();
        ((ISupportInitialize)this.customersButton).BeginInit();
        ((ISupportInitialize)this.templateGrid).BeginInit();
        ((ISupportInitialize)this.templateGrid.MasterTemplate).BeginInit();
        this.SuspendLayout();

        this.titleLabel.Name = "titleLabel";
        this.titleLabel.Text = "Email templates";
        this.titleLabel.Location = new Point(20, 12);
        this.titleLabel.Size = new Size(212, 41);

        this.providerLabel.Name = "providerLabel";
        this.providerLabel.Text = "Provider delivery unavailable offline.";
        this.providerLabel.Location = new Point(20, 55);
        this.providerLabel.Size = new Size(195, 24);

        this.searchBox.Name = "searchBox";
        this.searchBox.Location = new Point(20, 95);
        this.searchBox.Size = new Size(275, 27);

        this.disabledCheck.Name = "disabledCheck";
        this.disabledCheck.Text = "Include disabled";
        this.disabledCheck.Location = new Point(310, 95);
        this.disabledCheck.Size = new Size(153, 28);
        this.disabledCheck.CheckedChanged += this.RefreshClicked;

        this.refreshButton.Name = "refreshButton";
        this.refreshButton.Text = "Refresh";
        this.refreshButton.Location = new Point(470, 95);
        this.refreshButton.Size = new Size(90, 27);
        this.refreshButton.Click += this.RefreshClicked;

        this.newButton.Name = "newButton";
        this.newButton.Text = "New template";
        this.newButton.Location = new Point(570, 95);
        this.newButton.Size = new Size(111, 27);
        this.newButton.Click += this.NewClicked;
        this.newButton.Enabled = false;

        this.openButton.Name = "openButton";
        this.openButton.Text = "Open";
        this.openButton.Location = new Point(690, 95);
        this.openButton.Size = new Size(90, 27);
        this.openButton.Click += this.OpenClicked;
        this.openButton.Enabled = false;

        this.disableButton.Name = "disableButton";
        this.disableButton.Text = "Disable selected";
        this.disableButton.Location = new Point(790, 95);
        this.disableButton.Size = new Size(138, 27);
        this.disableButton.Click += this.DisableClicked;
        this.disableButton.Enabled = false;

        this.historyButton.Name = "historyButton";
        this.historyButton.Text = "Template history";
        this.historyButton.Anchor = AnchorStyles.Top | AnchorStyles.Right;
        this.historyButton.Location = new Point(790, 24);
        this.historyButton.Size = new Size(138, 27);
        this.historyButton.Click += this.HistoryClicked;
        this.historyButton.Enabled = false;

        this.composeButton.Name = "composeButton";
        this.composeButton.Text = "Compose email draft";
        this.composeButton.Anchor = AnchorStyles.Top | AnchorStyles.Right;
        this.composeButton.Location = new Point(630, 24);
        this.composeButton.Size = new Size(150, 27);
        this.composeButton.Click += this.ComposeClicked;
        this.composeButton.Enabled = false;

        this.draftsButton.Name = "draftsButton";
        this.draftsButton.Text = "Email drafts";
        this.draftsButton.Anchor = AnchorStyles.Top | AnchorStyles.Right;
        this.draftsButton.Location = new Point(500, 24);
        this.draftsButton.Size = new Size(120, 27);
        this.draftsButton.Click += this.DraftsClicked;
        this.draftsButton.Enabled = false;

        this.deliveryButton.Name = "deliveryButton";
        this.deliveryButton.Text = "Delivery history";
        this.deliveryButton.Anchor = AnchorStyles.Top | AnchorStyles.Right;
        this.deliveryButton.Location = new Point(360, 24);
        this.deliveryButton.Size = new Size(131, 27);
        this.deliveryButton.Click += this.DeliveryClicked;
        this.deliveryButton.Enabled = false;

        this.customersButton.Name = "customersButton";
        this.customersButton.Text = "Customer notes";
        this.customersButton.Anchor = AnchorStyles.Top | AnchorStyles.Right;
        this.customersButton.Location = new Point(790, 55);
        this.customersButton.Size = new Size(138, 27);
        this.customersButton.Click += this.CustomersClicked;
        this.customersButton.Enabled = false;

        this.campaignsButton.Name = "campaignsButton";
        this.campaignsButton.Text = "Campaigns";
        this.campaignsButton.Anchor = AnchorStyles.Top | AnchorStyles.Right;
        this.campaignsButton.Location = new Point(240, 24);
        this.campaignsButton.Size = new Size(111, 27);
        this.campaignsButton.Enabled = false;
        this.campaignsButton.Click += this.CampaignsClicked;

        this.autoResponsesButton.Name = "autoResponsesButton";
        this.autoResponsesButton.Text = "Auto-response rules";
        this.autoResponsesButton.Anchor = AnchorStyles.Top | AnchorStyles.Right;
        this.autoResponsesButton.Location = new Point(360, 55);
        this.autoResponsesButton.Size = new Size(140, 27);
        this.autoResponsesButton.Enabled = false;
        this.autoResponsesButton.Click += this.AutoResponsesClicked;

        this.webformsButton.Name = "webformsButton";
        this.webformsButton.Text = "Customer webforms";
        this.webformsButton.Anchor = AnchorStyles.Top | AnchorStyles.Right;
        this.webformsButton.Location = new Point(220, 55);
        this.webformsButton.Size = new Size(130, 27);
        this.webformsButton.Enabled = false;
        this.webformsButton.Click += this.WebformsClicked;

        this.favoritesOnlyCheck.Name = "favoritesOnlyCheck";
        this.favoritesOnlyCheck.Text = "Favorites only";
        this.favoritesOnlyCheck.Anchor = AnchorStyles.Top | AnchorStyles.Right;
        this.favoritesOnlyCheck.Location = new Point(510, 55);
        this.favoritesOnlyCheck.Size = new Size(121, 27);
        this.favoritesOnlyCheck.CheckedChanged += this.RefreshClicked;

        this.favoriteButton.Name = "favoriteButton";
        this.favoriteButton.Text = "Favorite template";
        this.favoriteButton.Anchor = AnchorStyles.Top | AnchorStyles.Right;
        this.favoriteButton.Location = new Point(640, 55);
        this.favoriteButton.Size = new Size(138, 27);
        this.favoriteButton.Enabled = false;
        this.favoriteButton.Click += this.FavoriteClicked;

        this.statusLabel.Name = "statusLabel";
        this.statusLabel.Location = new Point(20, 610);
        this.statusLabel.Size = new Size(908, 29);

        this.titleLabel.Font = new Font("Segoe UI Semibold", 22F);
        this.searchBox.NullText = "Search name or subject";
        this.searchBox.AccessibleName = "Template name or subject";
        this.searchBox.MaxLength = 240;
        this.statusLabel.Anchor = AnchorStyles.Left | AnchorStyles.Bottom | AnchorStyles.Right;
        this.templateGrid.Name = "templateGrid";
        this.templateGrid.Location = new Point(20, 137);
        this.templateGrid.Size = new Size(908, 464);
        this.templateGrid.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Bottom;
        this.templateGrid.ReadOnly = true;
        this.templateGrid.MasterTemplate.AutoGenerateColumns = false;
        this.templateGrid.MasterTemplate.AllowAddNewRow = false;
        this.templateGrid.MasterTemplate.AllowDeleteRow = false;
        this.templateGrid.MasterTemplate.AllowEditRow = false;
        this.templateGrid.MasterTemplate.AutoSizeColumnsMode = GridViewAutoSizeColumnsMode.Fill;
        this.nameColumn.Name = "nameColumn";
        this.nameColumn.FieldName = "Name";
        this.nameColumn.HeaderText = "Template";
        this.nameColumn.Width = 245;
        this.subjectColumn.Name = "subjectColumn";
        this.subjectColumn.FieldName = "Subject";
        this.subjectColumn.HeaderText = "Subject";
        this.subjectColumn.Width = 290;
        this.moduleColumn.Name = "moduleColumn";
        this.moduleColumn.FieldName = "Module";
        this.moduleColumn.HeaderText = "Module";
        this.moduleColumn.Width = 95;
        this.activeColumn.Name = "activeColumn";
        this.activeColumn.FieldName = "Active";
        this.activeColumn.HeaderText = "Active";
        this.activeColumn.Width = 75;
        this.favoriteColumn.Name = "favoriteColumn";
        this.favoriteColumn.FieldName = "Favorite";
        this.favoriteColumn.HeaderText = "Favorite";
        this.favoriteColumn.Width = 75;
        this.updatedColumn.Name = "updatedColumn";
        this.updatedColumn.FieldName = "Updated";
        this.updatedColumn.HeaderText = "Updated";
        this.updatedColumn.Width = 145;
        this.updatedColumn.FormatString = "{0:g}";
        this.templateGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] {
            this.nameColumn, this.subjectColumn, this.moduleColumn, this.activeColumn, this.favoriteColumn, this.updatedColumn
        });
        this.templateGrid.SelectionChanged += this.SelectionChanged;

        this.Controls.Add(this.titleLabel);
        this.Controls.Add(this.providerLabel);
        this.Controls.Add(this.favoritesOnlyCheck);
        this.Controls.Add(this.favoriteButton);
        this.Controls.Add(this.searchBox);
        this.Controls.Add(this.disabledCheck);
        this.Controls.Add(this.refreshButton);
        this.Controls.Add(this.newButton);
        this.Controls.Add(this.openButton);
        this.Controls.Add(this.disableButton);
        this.Controls.Add(this.historyButton);
        this.Controls.Add(this.composeButton);
        this.Controls.Add(this.draftsButton);
        this.Controls.Add(this.deliveryButton);
        this.Controls.Add(this.customersButton);
        this.Controls.Add(this.campaignsButton);
        this.Controls.Add(this.autoResponsesButton);
        this.Controls.Add(this.webformsButton);
        this.Controls.Add(this.statusLabel);
        this.Controls.Add(this.templateGrid);
        this.AcceptButton = this.refreshButton;
        this.AutoScaleDimensions = new SizeF(96F, 96F);
        this.AutoScaleMode = AutoScaleMode.Dpi;
        this.ClientSize = new Size(948, 649);
        this.MinimumSize = new Size(965, 520);
        this.StartPosition = FormStartPosition.CenterParent;
        this.BackColor = Color.FromArgb(243, 246, 251);
        this.Font = new Font("Segoe UI", 10F);
        this.Text = "Business Suite | Communication Center";
        this.Name = "DocumentsAndCommunicationForm";
        this.Shown += this.RefreshClicked;
        ((ISupportInitialize)this.searchBox).EndInit();
        ((ISupportInitialize)this.refreshButton).EndInit();
        ((ISupportInitialize)this.newButton).EndInit();
        ((ISupportInitialize)this.openButton).EndInit();
        ((ISupportInitialize)this.disableButton).EndInit();
        ((ISupportInitialize)this.historyButton).EndInit();
        ((ISupportInitialize)this.composeButton).EndInit();
        ((ISupportInitialize)this.draftsButton).EndInit();
        ((ISupportInitialize)this.deliveryButton).EndInit();
        ((ISupportInitialize)this.customersButton).EndInit();
        ((ISupportInitialize)this.templateGrid.MasterTemplate).EndInit();
        ((ISupportInitialize)this.templateGrid).EndInit();
        this.ResumeLayout(false);
        this.PerformLayout();
    }

    private Label titleLabel;
    private Label providerLabel;
    private RadTextBox searchBox;
    private CheckBox disabledCheck;
    private RadButton refreshButton;
    private RadButton newButton;
    private RadButton openButton;
    private RadButton disableButton;
    private RadButton historyButton;
    private RadButton composeButton;
    private RadButton draftsButton;
    private RadButton deliveryButton;
    private RadButton customersButton;
    private RadButton campaignsButton;
    private RadButton autoResponsesButton;
    private RadButton webformsButton;
    private Label statusLabel;
    private RadGridView templateGrid;
    private CheckBox favoritesOnlyCheck;
    private RadButton favoriteButton;
    private GridViewCheckBoxColumn favoriteColumn;
    private GridViewTextBoxColumn nameColumn;
    private GridViewTextBoxColumn subjectColumn;
    private GridViewTextBoxColumn moduleColumn;
    private GridViewCheckBoxColumn activeColumn;
    private GridViewTextBoxColumn updatedColumn;
}
