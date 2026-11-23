using Telerik.WinControls.UI;

namespace Business_Suite;

partial class CommunicationCampaignForm
{
    private void InitializeComponent()
    {
        SuspendLayout();
        availability = new Label { Name="availability", Text="Prepare email campaigns offline. Sending and scheduling require a delivery provider.",
            Location=new Point(20,16), Size=new Size(930,25) };
        searchBox = new RadTextBox { Name="searchBox", Location=new Point(20,51), Size=new Size(259,28), MaxLength=180,
            NullText="Search campaigns", AccessibleName="Search campaigns" };
        refreshButton = new RadButton { Name="refreshButton", Text="Refresh", Location=new Point(286,51), Size=new Size(103,27) };
        refreshButton.Click += ReloadClicked;
        campaignGrid = new RadGridView { Name="campaignGrid", Location=new Point(20,90), Size=new Size(369,254),
            ReadOnly=true, ShowGroupPanel=false, AccessibleName="Email campaigns" };
        campaignGrid.MasterTemplate.AutoGenerateColumns=false;
        campaignGrid.MasterTemplate.AllowAddNewRow=false;
        campaignGrid.MasterTemplate.AllowDeleteRow=false;
        campaignGrid.MasterTemplate.AutoSizeColumnsMode=GridViewAutoSizeColumnsMode.Fill;
        campaignGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] {
            new GridViewTextBoxColumn { Name="campaignIdColumn", FieldName="Id", HeaderText="ID", Width=45 },
            new GridViewTextBoxColumn { Name="campaignNameColumn", FieldName="Name", HeaderText="Campaign", Width=223 },
            new GridViewTextBoxColumn { Name="campaignStateColumn", FieldName="State", HeaderText="Status", Width=86 }
        });
        campaignGrid.SelectionChanged += SelectionChanged;
        newButton = new RadButton { Name="newButton", Text="Create campaign", Location=new Point(783,50), Size=new Size(166,28), Enabled=false };
        newButton.Click += NewClicked;
        historyButton = new RadButton { Name="historyButton", Text="Campaign history", Location=new Point(605,50), Size=new Size(166,28), Enabled=false };
        historyButton.Click += HistoryClicked;
        nameLabel = new Label { Name="nameLabel", Text="Campaign name", Location=new Point(411,99), Size=new Size(140,23) };
        nameBox = new RadTextBox { Name="nameBox", Location=new Point(555,95), Size=new Size(394,27), MaxLength=180,
            AccessibleName="Campaign name", Enabled=false };
        nameBox.TextChanged += InputChanged;
        templateLabel = new Label { Name="templateLabel", Text="Email template", Location=new Point(411,138), Size=new Size(140,23) };
        templateBox = new ComboBox { Name="templateBox", Location=new Point(555,134), Size=new Size(394,27),
            DropDownStyle=ComboBoxStyle.DropDownList, AccessibleName="Email template", Enabled=false };
        templateBox.SelectedIndexChanged += InputChanged;
        sourceLabel = new Label { Name="sourceLabel", Text="Audience source", Location=new Point(411,177), Size=new Size(140,23) };
        sourceBox = new ComboBox { Name="sourceBox", Location=new Point(555,173), Size=new Size(224,27), DropDownStyle=ComboBoxStyle.DropDownList,
            AccessibleName="Audience source", Enabled=false };
        sourceBox.Items.AddRange(new object[] { "CRM leads", "CRM contacts" });
        sourceBox.SelectedIndexChanged += InputChanged;
        segmentLabel = new Label { Name="segmentLabel", Text="CRM status filter", Location=new Point(411,216), Size=new Size(140,23) };
        segmentBox = new RadTextBox { Name="segmentBox", Location=new Point(555,212), Size=new Size(394,27), MaxLength=80,
            NullText="Optional", AccessibleName="CRM status filter", Enabled=false };
        segmentBox.TextChanged += InputChanged;
        limitLabel = new Label { Name="limitLabel", Text="Maximum recipients", Location=new Point(411,255), Size=new Size(140,23) };
        limitBox = new NumericUpDown { Name="limitBox", Location=new Point(555,251), Size=new Size(104,27), Minimum=1, Maximum=50,
            Value=50, AccessibleName="Maximum recipients", Enabled=false };
        limitBox.ValueChanged += InputChanged;
        saveButton = new RadButton { Name="saveButton", Text="Review and save", Location=new Point(411,307), Size=new Size(166,29), Enabled=false };
        saveButton.Click += SaveClicked;
        cancelButton = new RadButton { Name="cancelButton", Text="Cancel campaign", Location=new Point(585,307), Size=new Size(169,29), Enabled=false };
        cancelButton.Click += CancelClicked;
        previewButton = new RadButton { Name="previewButton", Text="Preview saved audience", Location=new Point(762,307), Size=new Size(187,29), Enabled=false };
        previewButton.Click += PreviewClicked;
        audienceLabel = new Label { Name="audienceLabel", Text="Audience preview", Location=new Point(20,364), Size=new Size(522,24) };
        audienceGrid = new RadGridView { Name="audienceGrid", Location=new Point(20,395), Size=new Size(537,196),
            ReadOnly=true, ShowGroupPanel=false, AccessibleName="Campaign audience" };
        audienceGrid.MasterTemplate.AutoGenerateColumns=false;
        audienceGrid.MasterTemplate.AllowAddNewRow=false;
        audienceGrid.MasterTemplate.AllowDeleteRow=false;
        audienceGrid.MasterTemplate.AutoSizeColumnsMode=GridViewAutoSizeColumnsMode.Fill;
        audienceGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] {
            new GridViewTextBoxColumn { Name="audienceNameColumn", FieldName="Name", HeaderText="Recipient", Width=165 },
            new GridViewTextBoxColumn { Name="audienceEmailColumn", FieldName="Email", HeaderText="Email address", Width=226 },
            new GridViewTextBoxColumn { Name="audienceOutcomeColumn", FieldName="Outcome", HeaderText="Result", Width=132 }
        });
        sampleLabel = new Label { Name="sampleLabel", Text="Personalized sample", Location=new Point(574,364), Size=new Size(375,24) };
        sampleBox = new RadTextBox { Name="sampleBox", Location=new Point(574,395), Size=new Size(375,196), Multiline=true,
            ReadOnly=true, ScrollBars=ScrollBars.Vertical, AccessibleName="Personalized sample" };
        feedback = new Label { Name="feedback", Location=new Point(20,607), Size=new Size(929,46) };
        Controls.AddRange(new Control[] { availability,searchBox,refreshButton,campaignGrid,newButton,historyButton,nameLabel,nameBox,
            templateLabel,templateBox,sourceLabel,sourceBox,segmentLabel,segmentBox,limitLabel,limitBox,saveButton,cancelButton,
            previewButton,audienceLabel,audienceGrid,sampleLabel,sampleBox,feedback });
        ClientSize = new Size(968,658);
        AutoScaleMode = AutoScaleMode.Font;
        AutoScaleDimensions = new SizeF(7F,15F);
        Font = new Font("Segoe UI",9F);
        StartPosition = FormStartPosition.CenterParent;
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = MinimizeBox = ShowInTaskbar = false;
        Name = "CommunicationCampaignForm";
        Text = "Email campaigns";
        Shown += ReloadClicked;
        FormClosing += ClosingCampaigns;
        ResumeLayout(false);
        PerformLayout();
    }

    private Label availability, nameLabel, templateLabel, sourceLabel, segmentLabel, limitLabel, audienceLabel, sampleLabel, feedback;
    private RadTextBox searchBox, nameBox, segmentBox, sampleBox;
    private ComboBox templateBox, sourceBox;
    private NumericUpDown limitBox;
    private RadGridView campaignGrid, audienceGrid;
    private RadButton refreshButton, newButton, historyButton, saveButton, cancelButton, previewButton;
}
