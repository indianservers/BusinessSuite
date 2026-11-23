using Telerik.WinControls.UI;

namespace Business_Suite;

partial class CommunicationWebformDetailsForm
{
    private void InitializeComponent()
    {
        SuspendLayout();
        headerLabel = new Label { Name="headerLabel", Location=new Point(20,14), Size=new Size(690,45),
            Font=new Font("Segoe UI",12F,FontStyle.Bold), AutoEllipsis=true };
        summaryLabel = new Label { Name="summaryLabel", Location=new Point(20,65), Size=new Size(690,42),
            AutoEllipsis=true };
        fieldsGrid = new RadGridView { Name="fieldsGrid", Location=new Point(20,118), Size=new Size(690,230),
            ReadOnly=true, ShowGroupPanel=false, AccessibleName="Saved customer fields and CRM mappings" };
        fieldsGrid.MasterTemplate.AutoGenerateColumns=false;
        fieldsGrid.MasterTemplate.AllowAddNewRow=false;
        fieldsGrid.MasterTemplate.EnableSorting=false;
        fieldsGrid.MasterTemplate.AutoSizeColumnsMode=GridViewAutoSizeColumnsMode.Fill;
        fieldsGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] {
            new GridViewTextBoxColumn { Name="fieldLabelColumn", FieldName="Label", HeaderText="Field label", Width=157 },
            new GridViewTextBoxColumn { Name="fieldKeyColumn", FieldName="Key", HeaderText="Field key", Width=154 },
            new GridViewTextBoxColumn { Name="fieldTypeColumn", FieldName="Type", HeaderText="Input type", Width=125 },
            new GridViewTextBoxColumn { Name="fieldMappingColumn", FieldName="Mapping", HeaderText="CRM mapping", Width=155 },
            new GridViewCheckBoxColumn { Name="fieldRequiredColumn", FieldName="Required", HeaderText="Required", Width=82 }
        });
        statusLabel = new Label { Name="statusLabel", Location=new Point(20,365), Size=new Size(560,37) };
        closeButton = new RadButton { Name="closeButton", Text="Close", Location=new Point(585,365),
            Size=new Size(125,29), DialogResult=DialogResult.Cancel };
        Controls.AddRange(new Control[] { headerLabel,summaryLabel,fieldsGrid,statusLabel,closeButton });
        CancelButton=closeButton;
        ClientSize=new Size(730,412);
        AutoScaleMode=AutoScaleMode.Font;
        AutoScaleDimensions=new SizeF(7F,15F);
        Font=new Font("Segoe UI",9F);
        StartPosition=FormStartPosition.CenterParent;
        FormBorderStyle=FormBorderStyle.FixedDialog;
        MaximizeBox=MinimizeBox=ShowInTaskbar=false;
        Name="CommunicationWebformDetailsForm";
        Text="Webform configuration";
        ResumeLayout(false);
    }

    private Label headerLabel, summaryLabel, statusLabel;
    private RadGridView fieldsGrid;
    private RadButton closeButton;
}
