using Telerik.WinControls;
using Telerik.WinControls.UI;

namespace Business_Suite;

partial class CommunicationWebformsForm
{
    private void InitializeComponent()
    {
        SuspendLayout();
        availability = new Label { Text="Save form definitions as inactive drafts. Public submissions require the connected edition.",
            Location=new Point(20,14), Size=new Size(820,23) };
        searchBox = new RadTextBox { Name="searchBox", Location=new Point(20,46), Size=new Size(267,27),
            NullText="Search name or public slug", AccessibleName="Search webforms", MaxLength=180 };
        refreshButton = new RadButton { Name="refreshButton", Text="Refresh", Location=new Point(300,46), Size=new Size(110,27) };
        refreshButton.Click += RefreshClicked;
        detailsButton = new RadButton { Name="detailsButton", Text="View details", AccessibleName="View saved configuration", Location=new Point(415,46),
            Size=new Size(105,27), Enabled=false };
        detailsButton.Click += DetailsClicked;
        editButton = new RadButton { Name="editButton", Text="Edit form", Location=new Point(528,46),
            Size=new Size(108,27), Enabled=false };
        editButton.Click += EditClicked;
        publicationButton = new RadButton { Name="publicationButton", Text="Deactivate...", Location=new Point(645,46),
            Size=new Size(195,27), Enabled=false };
        publicationButton.Click += PublicationClicked;
        libraryGrid = new RadGridView { Name="libraryGrid", Location=new Point(20,85), Size=new Size(820,156),
            ReadOnly=true, ShowGroupPanel=false, AccessibleName="Saved customer webforms" };
        libraryGrid.CurrentRowChanged += SelectionChanged;
        libraryGrid.MasterTemplate.AutoGenerateColumns=false;
        libraryGrid.MasterTemplate.AutoSizeColumnsMode=GridViewAutoSizeColumnsMode.Fill;
        libraryGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] {
            new GridViewTextBoxColumn { Name="nameColumn", FieldName="Name", HeaderText="Name", Width=218 },
            new GridViewTextBoxColumn { Name="slugColumn", FieldName="Slug", HeaderText="Public slug", Width=218 },
            new GridViewTextBoxColumn { Name="targetColumn", FieldName="Target", HeaderText="CRM target", Width=130 },
            new GridViewCheckBoxColumn { Name="activeColumn", FieldName="Active", HeaderText="Active", Width=96 },
            new GridViewTextBoxColumn { Name="ruleColumn", FieldName="Rule", HeaderText="Rule ID", Width=100 }
        });
        nameLabel = new Label { Text="Webform name", Location=new Point(20,258), Size=new Size(120,22) };
        nameBox = new RadTextBox { Name="nameBox", Location=new Point(143,255), Size=new Size(276,27),
            AccessibleName="Webform name", MaxLength=180 };
        slugLabel = new Label { Text="Public URL slug", Location=new Point(438,258), Size=new Size(136,22) };
        slugBox = new RadTextBox { Name="slugBox", Location=new Point(582,255), Size=new Size(258,27),
            AccessibleName="Public URL slug", MaxLength=140 };
        targetLabel = new Label { Text="Create CRM record", Location=new Point(20,295), Size=new Size(122,22) };
        targetBox = new RadDropDownList { Name="targetBox", Location=new Point(143,292), Size=new Size(276,27),
            AccessibleName="Create CRM record", DropDownStyle=RadDropDownStyle.DropDownList };
        targetBox.Items.Add(new RadListDataItem { Text="Lead", Value="lead" });
        targetBox.Items.Add(new RadListDataItem { Text="Contact", Value="contact" });
        targetBox.SelectedIndex=0;
        ruleLabel = new Label { Text="Acknowledgement rule", Location=new Point(438,295), Size=new Size(140,22) };
        ruleBox = new RadDropDownList { Name="ruleBox", Location=new Point(582,292), Size=new Size(258,27),
            AccessibleName="Acknowledgement rule", DropDownStyle=RadDropDownStyle.DropDownList,
            DisplayMember="Name", ValueMember="Id" };
        fieldsLabel = new Label { Text="Customer fields and CRM mapping", Location=new Point(20,335), Size=new Size(280,22) };
        fieldsGrid = new RadGridView { Name="fieldsGrid", Location=new Point(20,367), Size=new Size(820,175),
            ShowGroupPanel=false, AccessibleName="Customer fields and CRM mapping" };
        fieldsGrid.MasterTemplate.AutoGenerateColumns=false;
        fieldsGrid.MasterTemplate.AllowAddNewRow=false;
        fieldsGrid.MasterTemplate.AllowDeleteRow=false;
        fieldsGrid.MasterTemplate.EnableSorting=false;
        fieldsGrid.MasterTemplate.AutoSizeColumnsMode=GridViewAutoSizeColumnsMode.Fill;
        fieldsGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] {
            new GridViewTextBoxColumn { Name="fieldLabelColumn", FieldName="Label", HeaderText="Field label", Width=205 },
            new GridViewTextBoxColumn { Name="fieldKeyColumn", FieldName="Key", HeaderText="Field key", Width=180 },
            new GridViewComboBoxColumn { Name="fieldTypeColumn", FieldName="Type", HeaderText="Input type", Width=174,
                DataSource=new string[] { "text","email","tel","textarea" }, DropDownStyle=RadDropDownStyle.DropDownList },
            new GridViewComboBoxColumn { Name="fieldMappingColumn", FieldName="Target", HeaderText="Map to CRM", Width=170,
                DataSource=new string[] { "first_name","last_name","email","phone","company_name","message" },
                DropDownStyle=RadDropDownStyle.DropDownList },
            new GridViewCheckBoxColumn { Name="fieldRequiredColumn", FieldName="Required", HeaderText="Required", Width=74 }
        });
        addButton = new RadButton { Name="addButton", Text="Add field", Location=new Point(576,330), Size=new Size(120,27) };
        addButton.Click += AddClicked;
        removeButton = new RadButton { Name="removeButton", Text="Remove field", Location=new Point(710,330), Size=new Size(130,27) };
        removeButton.Click += RemoveClicked;
        saveButton = new RadButton { Name="saveButton", Text="Review configuration", Location=new Point(661,553), Size=new Size(179,33) };
        saveButton.Click += SaveClicked;
        clearButton = new RadButton { Name="clearButton", Text="Clear new draft", Location=new Point(661,592),
            Size=new Size(179,28), Enabled=false };
        clearButton.Click += ClearDraftClicked;
        feedback = new Label { Name="feedback", Location=new Point(20,553), Size=new Size(623,78) };
        nameBox.TextChanged += InputChanged;
        slugBox.TextChanged += InputChanged;
        targetBox.SelectedIndexChanged += InputChanged;
        ruleBox.SelectedIndexChanged += InputChanged;
        fieldsGrid.CellValueChanged += FieldsChanged;
        Controls.AddRange(new Control[] { availability,searchBox,refreshButton,detailsButton,editButton,publicationButton,libraryGrid,nameLabel,nameBox,slugLabel,slugBox,
            targetLabel,targetBox,ruleLabel,ruleBox,fieldsLabel,addButton,removeButton,fieldsGrid,saveButton,clearButton,feedback });
        ClientSize=new Size(860,635);
        AutoScaleMode=AutoScaleMode.Font;
        AutoScaleDimensions=new SizeF(7F,15F);
        Font=new Font("Segoe UI",9F);
        StartPosition=FormStartPosition.CenterParent;
        FormBorderStyle=FormBorderStyle.FixedDialog;
        MaximizeBox=MinimizeBox=ShowInTaskbar=false;
        Name="CommunicationWebformsForm";
        Text="Customer webforms";
        Shown+=RefreshClicked;
        FormClosing+=ClosingWebforms;
        ResumeLayout(false);
    }

    private Label availability, nameLabel, slugLabel, targetLabel, ruleLabel, fieldsLabel, feedback;
    private RadTextBox searchBox, nameBox, slugBox;
    private RadGridView libraryGrid, fieldsGrid;
    private RadDropDownList targetBox, ruleBox;
    private RadButton refreshButton, detailsButton, editButton, publicationButton, addButton, removeButton, saveButton, clearButton;
}
