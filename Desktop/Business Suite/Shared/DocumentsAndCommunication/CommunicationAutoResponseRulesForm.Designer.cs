using Telerik.WinControls.UI;

namespace Business_Suite;

partial class CommunicationAutoResponseRulesForm
{
    private void InitializeComponent()
    {
        SuspendLayout();
        availability = new Label { Name="availability", Text="Prepare email acknowledgements here. Public submissions and delivery require the connected edition.",
            Location=new Point(20,14), Size=new Size(742,28) };
        searchBox = new RadTextBox { Name="searchBox", Location=new Point(20,50), Size=new Size(580,27), MaxLength=180,
            NullText="Search auto-response rules", AccessibleName="Search auto-response rules" };
        refreshButton = new RadButton { Name="refreshButton", Text="Refresh", Location=new Point(616,50), Size=new Size(147,27) };
        refreshButton.Click += RefreshClicked;
        grid = new RadGridView { Name="grid", Location=new Point(20,87), Size=new Size(743,221), ReadOnly=true,
            ShowGroupPanel=false, AccessibleName="Auto-response rules" };
        grid.MasterTemplate.AutoGenerateColumns=false;
        grid.MasterTemplate.AllowAddNewRow=false;
        grid.MasterTemplate.AllowDeleteRow=false;
        grid.MasterTemplate.AutoSizeColumnsMode=GridViewAutoSizeColumnsMode.Fill;
        grid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] {
            new GridViewTextBoxColumn { Name="idColumn", FieldName="Id", HeaderText="ID", Width=55 },
            new GridViewTextBoxColumn { Name="nameColumn", FieldName="Name", HeaderText="Rule", Width=313 },
            new GridViewTextBoxColumn { Name="triggerColumn", FieldName="Trigger", HeaderText="Trigger", Width=210 },
            new GridViewTextBoxColumn { Name="templateColumn", FieldName="Template", HeaderText="Template", Width=90 },
            new GridViewCheckBoxColumn { Name="activeColumn", FieldName="Active", HeaderText="Active", Width=63 }
        });
        nameLabel = new Label { Name="nameLabel", Text="Rule name", Location=new Point(20,326), Size=new Size(170,23) };
        nameBox = new RadTextBox { Name="nameBox", Location=new Point(194,322), Size=new Size(569,27), MaxLength=180,
            AccessibleName="Rule name", Enabled=false };
        nameBox.TextChanged += InputChanged;
        templateLabel = new Label { Name="templateLabel", Text="Acknowledgement template", Location=new Point(20,365), Size=new Size(170,23) };
        templateBox = new ComboBox { Name="templateBox", Location=new Point(194,361), Size=new Size(569,27),
            DropDownStyle=ComboBoxStyle.DropDownList, AccessibleName="Acknowledgement template", Enabled=false };
        templateBox.SelectedIndexChanged += InputChanged;
        triggerLabel = new Label { Name="triggerLabel", Text="Trigger: Webform submission", Location=new Point(20,408), Size=new Size(300,22) };
        activeBox = new CheckBox { Name="activeBox", Text="Active rule", Location=new Point(336,404), Size=new Size(167,29), Enabled=false };
        activeBox.CheckedChanged += InputChanged;
        saveButton = new RadButton { Name="saveButton", Text="Review rule", Location=new Point(595,403), Size=new Size(168,29), Enabled=false };
        saveButton.Click += SaveClicked;
        feedback = new Label { Name="feedback", Location=new Point(20,449), Size=new Size(743,42) };
        Controls.AddRange(new Control[] { availability,searchBox,refreshButton,grid,nameLabel,nameBox,templateLabel,
            templateBox,triggerLabel,activeBox,saveButton,feedback });
        ClientSize=new Size(783,500);
        AutoScaleMode=AutoScaleMode.Font;
        AutoScaleDimensions=new SizeF(7F,15F);
        Font=new Font("Segoe UI",9F);
        StartPosition=FormStartPosition.CenterParent;
        FormBorderStyle=FormBorderStyle.FixedDialog;
        MaximizeBox=MinimizeBox=ShowInTaskbar=false;
        Name="CommunicationAutoResponseRulesForm";
        Text="Email auto-response rules";
        Shown+=RefreshClicked;
        FormClosing+=ClosingRules;
        ResumeLayout(false);
        PerformLayout();
    }

    private Label availability, nameLabel, templateLabel, triggerLabel, feedback;
    private RadTextBox searchBox, nameBox;
    private RadGridView grid;
    private ComboBox templateBox;
    private CheckBox activeBox;
    private RadButton refreshButton, saveButton;
}
