using Telerik.WinControls.UI;

namespace Business_Suite;

partial class CommunicationCampaignHistoryForm
{
    private void InitializeComponent()
    {
        SuspendLayout();
        heading = new Label { Name="heading", Text="Campaign history", Location=new Point(20,15), Size=new Size(745,29),
            Font=new Font("Segoe UI Semibold", 13F), AutoEllipsis=true };
        refreshButton = new RadButton { Name="refreshButton", Text="Refresh", Location=new Point(779,15), Size=new Size(117,28),
            Anchor=AnchorStyles.Top|AnchorStyles.Right };
        refreshButton.Click += RefreshClicked;
        tabs = new RadPageView { Name="tabs", Location=new Point(20,58), Size=new Size(876,448),
            Anchor=AnchorStyles.Top|AnchorStyles.Bottom|AnchorStyles.Left|AnchorStyles.Right };
        ((RadPageViewStripElement)tabs.ViewElement).StripButtons = StripViewButtons.None;
        deliveryPage = new RadPageViewPage { Name="deliveryPage", Text="Delivery records" };
        changesPage = new RadPageViewPage { Name="changesPage", Text="Campaign changes" };
        deliveriesGrid = new RadGridView { Name="deliveriesGrid", Dock=DockStyle.Fill, ReadOnly=true, ShowGroupPanel=false };
        deliveriesGrid.MasterTemplate.AutoGenerateColumns=false;
        deliveriesGrid.MasterTemplate.AllowAddNewRow=false;
        deliveriesGrid.MasterTemplate.AllowDeleteRow=false;
        deliveriesGrid.MasterTemplate.AutoSizeColumnsMode=GridViewAutoSizeColumnsMode.Fill;
        deliveriesGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] {
            new GridViewDateTimeColumn { Name="recordedColumn", FieldName="Recorded", HeaderText="Recorded", Width=132, FormatString="{0:g}" },
            new GridViewTextBoxColumn { Name="recipientColumn", FieldName="Recipient", HeaderText="Recipient", Width=134 },
            new GridViewTextBoxColumn { Name="emailColumn", FieldName="Email", HeaderText="Email address", Width=172 },
            new GridViewTextBoxColumn { Name="originColumn", FieldName="Channel", HeaderText="Source", Width=118 },
            new GridViewTextBoxColumn { Name="statusColumn", FieldName="Status", HeaderText="Status", Width=87 },
            new GridViewTextBoxColumn { Name="noteColumn", FieldName="Note", HeaderText="Notes", Width=174 }
        });
        changesGrid = new RadGridView { Name="changesGrid", Dock=DockStyle.Fill, ReadOnly=true, ShowGroupPanel=false };
        changesGrid.MasterTemplate.AutoGenerateColumns=false;
        changesGrid.MasterTemplate.AllowAddNewRow=false;
        changesGrid.MasterTemplate.AllowDeleteRow=false;
        changesGrid.MasterTemplate.AutoSizeColumnsMode=GridViewAutoSizeColumnsMode.Fill;
        changesGrid.MasterTemplate.Columns.AddRange(new GridViewDataColumn[] {
            new GridViewDateTimeColumn { Name="changeTimeColumn", FieldName="Recorded", HeaderText="Recorded", Width=174, FormatString="{0:g}" },
            new GridViewTextBoxColumn { Name="changeColumn", FieldName="Change", HeaderText="Change", Width=164 },
            new GridViewTextBoxColumn { Name="actorColumn", FieldName="ActorId", HeaderText="Actor ID", Width=112 },
            new GridViewTextBoxColumn { Name="nameColumn", FieldName="Name", HeaderText="Campaign name", Width=370 }
        });
        deliveryStatus = new Label { Name="deliveryStatus", Dock=DockStyle.Bottom, Height=32, Padding=new Padding(6,5,0,0) };
        changesStatus = new Label { Name="changesStatus", Dock=DockStyle.Bottom, Height=32, Padding=new Padding(6,5,0,0) };
        deliveryPage.Controls.AddRange(new Control[]{ deliveriesGrid,deliveryStatus });
        changesPage.Controls.AddRange(new Control[]{ changesGrid,changesStatus });
        tabs.Pages.Add(deliveryPage);
        tabs.Pages.Add(changesPage);
        Controls.AddRange(new Control[]{ heading,refreshButton,tabs });
        ClientSize=new Size(916,526);
        MinimumSize=new Size(855,490);
        AutoScaleMode=AutoScaleMode.Font;
        AutoScaleDimensions=new SizeF(7F,15F);
        Font=new Font("Segoe UI",9F);
        StartPosition=FormStartPosition.CenterParent;
        ShowInTaskbar=MinimizeBox=MaximizeBox=false;
        Name="CommunicationCampaignHistoryForm";
        Text="Campaign history";
        Shown+=RefreshClicked;
        ResumeLayout(false);
        PerformLayout();
    }

    private Label heading, deliveryStatus, changesStatus;
    private RadButton refreshButton;
    private RadPageView tabs;
    private RadPageViewPage deliveryPage, changesPage;
    private RadGridView deliveriesGrid, changesGrid;
}
