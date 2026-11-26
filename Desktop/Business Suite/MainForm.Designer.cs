#nullable disable
using System.ComponentModel;
using System.Drawing;
using System.Windows.Forms;
using Telerik.WinControls;
using Telerik.WinControls.UI;

namespace Business_Suite
{
    partial class MainForm
    {
        private void InitializeComponent()
        {
            System.ComponentModel.ComponentResourceManager resources = new System.ComponentModel.ComponentResourceManager(typeof(MainForm));
            this.ribbonBar = new Telerik.WinControls.UI.RadRibbonBar();
            this.homeTab = new Telerik.WinControls.UI.RibbonTab();
            this.workspaceGroup = new Telerik.WinControls.UI.RadRibbonBarGroup();
            this.homeHomeRibbonButton = new Telerik.WinControls.UI.RadButtonElement();
            this.appointmentsTab = new Telerik.WinControls.UI.RibbonTab();
            this.appointmentsGroup = new Telerik.WinControls.UI.RadRibbonBarGroup();
            this.appointmentSchedulerRibbonButton = new Telerik.WinControls.UI.RadButtonElement();
            this.crmTab = new Telerik.WinControls.UI.RibbonTab();
            this.crmGroup = new Telerik.WinControls.UI.RadRibbonBarGroup();
            this.crmWorkspaceRibbonButton = new Telerik.WinControls.UI.RadButtonElement();
            this.companiesRibbonButton = new Telerik.WinControls.UI.RadButtonElement();
            this.contactsRibbonButton = new Telerik.WinControls.UI.RadButtonElement();
            this.crmPipelineGroup = new Telerik.WinControls.UI.RadRibbonBarGroup();
            this.leadsRibbonButton = new Telerik.WinControls.UI.RadButtonElement();
            this.dealsRibbonButton = new Telerik.WinControls.UI.RadButtonElement();
            this.financeTab = new Telerik.WinControls.UI.RibbonTab();
            this.financeGroup = new Telerik.WinControls.UI.RadRibbonBarGroup();
            this.financeWorkspaceRibbonButton = new Telerik.WinControls.UI.RadButtonElement();
            this.financeLedgersRibbonButton = new Telerik.WinControls.UI.RadButtonElement();
            this.financeWorkspacesRibbonButton = new Telerik.WinControls.UI.RadButtonElement();
            this.hrmsTab = new Telerik.WinControls.UI.RibbonTab();
            this.hrmsGroup = new Telerik.WinControls.UI.RadRibbonBarGroup();
            this.hrWorkspaceRibbonButton = new Telerik.WinControls.UI.RadButtonElement();
            this.hrWorkspacesRibbonButton = new Telerik.WinControls.UI.RadButtonElement();
            this.projectsTab = new Telerik.WinControls.UI.RibbonTab();
            this.projectsGroup = new Telerik.WinControls.UI.RadRibbonBarGroup();
            this.projectWorkspaceRibbonButton = new Telerik.WinControls.UI.RadButtonElement();
            this.projectWorkspacesRibbonButton = new Telerik.WinControls.UI.RadButtonElement();
            this.projectMyWorkRibbonButton = new Telerik.WinControls.UI.RadButtonElement();
            this.salesTab = new Telerik.WinControls.UI.RibbonTab();
            this.salesGroup = new Telerik.WinControls.UI.RadRibbonBarGroup();
            this.salesWorkspaceRibbonButton = new Telerik.WinControls.UI.RadButtonElement();
            this.salesAppointmentsRibbonButton = new Telerik.WinControls.UI.RadButtonElement();
            this.sharedTab = new Telerik.WinControls.UI.RibbonTab();
            this.sharedGroup = new Telerik.WinControls.UI.RadRibbonBarGroup();
            this.sharedDataRibbonButton = new Telerik.WinControls.UI.RadButtonElement();
            this.sharedDocumentsRibbonButton = new Telerik.WinControls.UI.RadButtonElement();
            this.administrationTab = new Telerik.WinControls.UI.RibbonTab();
            this.companyGroup = new Telerik.WinControls.UI.RadRibbonBarGroup();
            this.administrationAdministrationRibbonButton = new Telerik.WinControls.UI.RadButtonElement();
            this.administrationLocalCompaniesRibbonButton = new Telerik.WinControls.UI.RadButtonElement();
            this.toolsTab = new Telerik.WinControls.UI.RibbonTab();
            this.toolsGroup = new Telerik.WinControls.UI.RadRibbonBarGroup();
            this.toolsSettingsRibbonButton = new Telerik.WinControls.UI.RadButtonElement();
            this.toolsPowerRibbonButton = new Telerik.WinControls.UI.RadButtonElement();
            this.reportsTab = new Telerik.WinControls.UI.RibbonTab();
            this.reportingGroup = new Telerik.WinControls.UI.RadRibbonBarGroup();
            this.reportsReportingRibbonButton = new Telerik.WinControls.UI.RadButtonElement();
            this.helpTab = new Telerik.WinControls.UI.RibbonTab();
            this.helpGroup = new Telerik.WinControls.UI.RadRibbonBarGroup();
            this.helpHelpRibbonButton = new Telerik.WinControls.UI.RadButtonElement();
            this.workspaces = new Business_Suite.WorkspaceTabControl();
            this.homePage = new System.Windows.Forms.TabPage();
            this.homeBody = new System.Windows.Forms.Panel();
            this.homeContent = new System.Windows.Forms.Panel();
            this.sharedCards = new System.Windows.Forms.FlowLayoutPanel();
            this.dataCard = new Business_Suite.WorkspaceCard();
            this.administrationCard = new Business_Suite.WorkspaceCard();
            this.documentsCard = new Business_Suite.WorkspaceCard();
            this.powerCard = new Business_Suite.WorkspaceCard();
            this.reportingCard = new Business_Suite.WorkspaceCard();
            this.localCompaniesCard = new Business_Suite.WorkspaceCard();
            this.sharedHeadingLabel = new System.Windows.Forms.Label();
            this.modulesCards = new System.Windows.Forms.FlowLayoutPanel();
            this.appointmentsCard = new Business_Suite.WorkspaceCard();
            this.crmCard = new Business_Suite.WorkspaceCard();
            this.financeCard = new Business_Suite.WorkspaceCard();
            this.hrmsCard = new Business_Suite.WorkspaceCard();
            this.projectsCard = new Business_Suite.WorkspaceCard();
            this.salesCard = new Business_Suite.WorkspaceCard();
            this.modulesHeadingLabel = new System.Windows.Forms.Label();
            this.homeHeader = new Business_Suite.WorkspaceHeader();
            this.homeTitleLabel = new System.Windows.Forms.Label();
            this.homeDescriptionLabel = new System.Windows.Forms.Label();
            this.appointmentsPage = new System.Windows.Forms.TabPage();
            this.appointmentsBody = new System.Windows.Forms.Panel();
            this.appointmentsContent = new System.Windows.Forms.Panel();
            this.appointmentsCards = new System.Windows.Forms.FlowLayoutPanel();
            this.appointmentSchedulerCard = new Business_Suite.WorkspaceCard();
            this.appointmentsHeader = new Business_Suite.WorkspaceHeader();
            this.appointmentsHeaderIcon = new System.Windows.Forms.PictureBox();
            this.appointmentsTitleLabel = new System.Windows.Forms.Label();
            this.appointmentsDescriptionLabel = new System.Windows.Forms.Label();
            this.crmPage = new System.Windows.Forms.TabPage();
            this.crmBody = new System.Windows.Forms.Panel();
            this.crmContent = new System.Windows.Forms.Panel();
            this.crmCards = new System.Windows.Forms.FlowLayoutPanel();
            this.crmWorkspaceCard = new Business_Suite.WorkspaceCard();
            this.companiesCard = new Business_Suite.WorkspaceCard();
            this.contactsCard = new Business_Suite.WorkspaceCard();
            this.leadsCard = new Business_Suite.WorkspaceCard();
            this.dealsCard = new Business_Suite.WorkspaceCard();
            this.crmHeader = new Business_Suite.WorkspaceHeader();
            this.crmHeaderIcon = new System.Windows.Forms.PictureBox();
            this.crmTitleLabel = new System.Windows.Forms.Label();
            this.crmDescriptionLabel = new System.Windows.Forms.Label();
            this.financePage = new System.Windows.Forms.TabPage();
            this.financeBody = new System.Windows.Forms.Panel();
            this.financeContent = new System.Windows.Forms.Panel();
            this.financeCards = new System.Windows.Forms.FlowLayoutPanel();
            this.financeWorkspaceCard = new Business_Suite.WorkspaceCard();
            this.financeLedgersCard = new Business_Suite.WorkspaceCard();
            this.financeWorkspacesCard = new Business_Suite.WorkspaceCard();
            this.financeHeader = new Business_Suite.WorkspaceHeader();
            this.financeHeaderIcon = new System.Windows.Forms.PictureBox();
            this.financeTitleLabel = new System.Windows.Forms.Label();
            this.financeDescriptionLabel = new System.Windows.Forms.Label();
            this.hrmsPage = new System.Windows.Forms.TabPage();
            this.hrmsBody = new System.Windows.Forms.Panel();
            this.hrmsContent = new System.Windows.Forms.Panel();
            this.hrmsCards = new System.Windows.Forms.FlowLayoutPanel();
            this.hrWorkspaceCard = new Business_Suite.WorkspaceCard();
            this.hrWorkspacesCard = new Business_Suite.WorkspaceCard();
            this.hrmsHeader = new Business_Suite.WorkspaceHeader();
            this.hrmsHeaderIcon = new System.Windows.Forms.PictureBox();
            this.hrmsTitleLabel = new System.Windows.Forms.Label();
            this.hrmsDescriptionLabel = new System.Windows.Forms.Label();
            this.projectsPage = new System.Windows.Forms.TabPage();
            this.projectsBody = new System.Windows.Forms.Panel();
            this.projectsContent = new System.Windows.Forms.Panel();
            this.projectsCards = new System.Windows.Forms.FlowLayoutPanel();
            this.projectWorkspaceCard = new Business_Suite.WorkspaceCard();
            this.projectWorkspacesCard = new Business_Suite.WorkspaceCard();
            this.projectMyWorkCard = new Business_Suite.WorkspaceCard();
            this.projectsHeader = new Business_Suite.WorkspaceHeader();
            this.projectsHeaderIcon = new System.Windows.Forms.PictureBox();
            this.projectsTitleLabel = new System.Windows.Forms.Label();
            this.projectsDescriptionLabel = new System.Windows.Forms.Label();
            this.salesPage = new System.Windows.Forms.TabPage();
            this.salesBody = new System.Windows.Forms.Panel();
            this.salesContent = new System.Windows.Forms.Panel();
            this.salesCards = new System.Windows.Forms.FlowLayoutPanel();
            this.salesWorkspaceCard = new Business_Suite.WorkspaceCard();
            this.salesAppointmentsCard = new Business_Suite.WorkspaceCard();
            this.salesHeader = new Business_Suite.WorkspaceHeader();
            this.salesHeaderIcon = new System.Windows.Forms.PictureBox();
            this.salesTitleLabel = new System.Windows.Forms.Label();
            this.salesDescriptionLabel = new System.Windows.Forms.Label();
            ((System.ComponentModel.ISupportInitialize)(this.ribbonBar)).BeginInit();
            this.workspaces.SuspendLayout();
            this.homePage.SuspendLayout();
            this.homeBody.SuspendLayout();
            this.homeContent.SuspendLayout();
            this.sharedCards.SuspendLayout();
            this.modulesCards.SuspendLayout();
            this.homeHeader.SuspendLayout();
            this.appointmentsPage.SuspendLayout();
            this.appointmentsBody.SuspendLayout();
            this.appointmentsContent.SuspendLayout();
            this.appointmentsCards.SuspendLayout();
            this.appointmentsHeader.SuspendLayout();
            ((System.ComponentModel.ISupportInitialize)(this.appointmentsHeaderIcon)).BeginInit();
            this.crmPage.SuspendLayout();
            this.crmBody.SuspendLayout();
            this.crmContent.SuspendLayout();
            this.crmCards.SuspendLayout();
            this.crmHeader.SuspendLayout();
            ((System.ComponentModel.ISupportInitialize)(this.crmHeaderIcon)).BeginInit();
            this.financePage.SuspendLayout();
            this.financeBody.SuspendLayout();
            this.financeContent.SuspendLayout();
            this.financeCards.SuspendLayout();
            this.financeHeader.SuspendLayout();
            ((System.ComponentModel.ISupportInitialize)(this.financeHeaderIcon)).BeginInit();
            this.hrmsPage.SuspendLayout();
            this.hrmsBody.SuspendLayout();
            this.hrmsContent.SuspendLayout();
            this.hrmsCards.SuspendLayout();
            this.hrmsHeader.SuspendLayout();
            ((System.ComponentModel.ISupportInitialize)(this.hrmsHeaderIcon)).BeginInit();
            this.projectsPage.SuspendLayout();
            this.projectsBody.SuspendLayout();
            this.projectsContent.SuspendLayout();
            this.projectsCards.SuspendLayout();
            this.projectsHeader.SuspendLayout();
            ((System.ComponentModel.ISupportInitialize)(this.projectsHeaderIcon)).BeginInit();
            this.salesPage.SuspendLayout();
            this.salesBody.SuspendLayout();
            this.salesContent.SuspendLayout();
            this.salesCards.SuspendLayout();
            this.salesHeader.SuspendLayout();
            ((System.ComponentModel.ISupportInitialize)(this.salesHeaderIcon)).BeginInit();
            this.SuspendLayout();
            // 
            // ribbonBar
            // 
            this.ribbonBar.CommandTabs.AddRange(new Telerik.WinControls.RadItem[] {
            this.homeTab,
            this.appointmentsTab,
            this.crmTab,
            this.financeTab,
            this.hrmsTab,
            this.projectsTab,
            this.salesTab,
            this.sharedTab,
            this.administrationTab,
            this.toolsTab,
            this.reportsTab,
            this.helpTab});
            // 
            // 
            // 
            this.ribbonBar.ExitButton.Text = "Exit";
            this.ribbonBar.LocalizationSettings.LayoutModeText = "Simplified Layout";
            this.ribbonBar.Location = new System.Drawing.Point(0, 0);
            this.ribbonBar.Name = "ribbonBar";
            // 
            // 
            // 
            this.ribbonBar.OptionsButton.Text = "Options";
            this.ribbonBar.ShowExpandButton = false;
            this.ribbonBar.Size = new System.Drawing.Size(1400, 146);
            this.ribbonBar.TabIndex = 1;
            this.ribbonBar.Text = "Business Suite";
            ((Telerik.WinControls.UI.RadRibbonBarCaption)(this.ribbonBar.GetChildAt(0).GetChildAt(3))).Visibility = Telerik.WinControls.ElementVisibility.Collapsed;
            ((Telerik.WinControls.UI.RadApplicationMenuButtonElement)(this.ribbonBar.GetChildAt(0).GetChildAt(5))).Visibility = Telerik.WinControls.ElementVisibility.Collapsed;
            // 
            // homeTab
            // 
            this.homeTab.IsSelected = true;
            this.homeTab.Items.AddRange(new Telerik.WinControls.RadItem[] {
            this.workspaceGroup});
            this.homeTab.Name = "homeTab";
            this.homeTab.Text = "Home";
            this.homeTab.UseMnemonic = false;
            // 
            // workspaceGroup
            // 
            this.workspaceGroup.Items.AddRange(new Telerik.WinControls.RadItem[] {
            this.homeHomeRibbonButton});
            this.workspaceGroup.Name = "workspaceGroup";
            this.workspaceGroup.Text = "Workspace";
            // 
            // homeHomeRibbonButton
            // 
            this.homeHomeRibbonButton.AccessibleDescription = "Return to the home workspace";
            this.homeHomeRibbonButton.DisplayStyle = Telerik.WinControls.DisplayStyle.ImageAndText;
            this.homeHomeRibbonButton.Image = ((System.Drawing.Image)(resources.GetObject("homeHomeRibbonButton.Image")));
            this.homeHomeRibbonButton.ImageAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.homeHomeRibbonButton.MaxSize = new System.Drawing.Size(112, 86);
            this.homeHomeRibbonButton.MinSize = new System.Drawing.Size(104, 80);
            this.homeHomeRibbonButton.Name = "homeHomeRibbonButton";
            this.homeHomeRibbonButton.Padding = new System.Windows.Forms.Padding(3);
            this.homeHomeRibbonButton.Text = "Home";
            this.homeHomeRibbonButton.TextAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.homeHomeRibbonButton.TextImageRelation = System.Windows.Forms.TextImageRelation.ImageAboveText;
            this.homeHomeRibbonButton.TextWrap = true;
            this.homeHomeRibbonButton.ToolTipText = "Home";
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.homeHomeRibbonButton.GetChildAt(1).GetChildAt(1))).AutoEllipsis = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.homeHomeRibbonButton.GetChildAt(1).GetChildAt(1))).TextWrap = true;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.homeHomeRibbonButton.GetChildAt(1).GetChildAt(1))).UseMnemonic = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.homeHomeRibbonButton.GetChildAt(1).GetChildAt(1))).LineLimit = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.homeHomeRibbonButton.GetChildAt(1).GetChildAt(1))).Alignment = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // appointmentsTab
            // 
            this.appointmentsTab.Items.AddRange(new Telerik.WinControls.RadItem[] {
            this.appointmentsGroup});
            this.appointmentsTab.Name = "appointmentsTab";
            this.appointmentsTab.Text = "Appointments";
            this.appointmentsTab.UseMnemonic = false;
            // 
            // appointmentsGroup
            // 
            this.appointmentsGroup.Items.AddRange(new Telerik.WinControls.RadItem[] {
            this.appointmentSchedulerRibbonButton});
            this.appointmentsGroup.Name = "appointmentsGroup";
            this.appointmentsGroup.Text = "Schedule";
            // 
            // appointmentSchedulerRibbonButton
            // 
            this.appointmentSchedulerRibbonButton.AccessibleDescription = "Open the appointment scheduler";
            this.appointmentSchedulerRibbonButton.DisplayStyle = Telerik.WinControls.DisplayStyle.ImageAndText;
            this.appointmentSchedulerRibbonButton.Image = ((System.Drawing.Image)(resources.GetObject("appointmentSchedulerRibbonButton.Image")));
            this.appointmentSchedulerRibbonButton.ImageAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.appointmentSchedulerRibbonButton.MaxSize = new System.Drawing.Size(112, 86);
            this.appointmentSchedulerRibbonButton.MinSize = new System.Drawing.Size(104, 80);
            this.appointmentSchedulerRibbonButton.Name = "appointmentSchedulerRibbonButton";
            this.appointmentSchedulerRibbonButton.Padding = new System.Windows.Forms.Padding(3);
            this.appointmentSchedulerRibbonButton.Text = "Appointment\nscheduler";
            this.appointmentSchedulerRibbonButton.TextAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.appointmentSchedulerRibbonButton.TextImageRelation = System.Windows.Forms.TextImageRelation.ImageAboveText;
            this.appointmentSchedulerRibbonButton.TextWrap = true;
            this.appointmentSchedulerRibbonButton.ToolTipText = "Appointment scheduler";
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.appointmentSchedulerRibbonButton.GetChildAt(1).GetChildAt(1))).AutoEllipsis = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.appointmentSchedulerRibbonButton.GetChildAt(1).GetChildAt(1))).TextWrap = true;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.appointmentSchedulerRibbonButton.GetChildAt(1).GetChildAt(1))).UseMnemonic = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.appointmentSchedulerRibbonButton.GetChildAt(1).GetChildAt(1))).Alignment = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // crmTab
            // 
            this.crmTab.Items.AddRange(new Telerik.WinControls.RadItem[] {
            this.crmGroup,
            this.crmPipelineGroup});
            this.crmTab.Name = "crmTab";
            this.crmTab.Text = "VyaparaCRM";
            this.crmTab.UseMnemonic = false;
            // 
            // crmGroup
            // 
            this.crmGroup.Items.AddRange(new Telerik.WinControls.RadItem[] {
            this.crmWorkspaceRibbonButton,
            this.companiesRibbonButton,
            this.contactsRibbonButton});
            this.crmGroup.Name = "crmGroup";
            this.crmGroup.Text = "Customers";
            // 
            // crmWorkspaceRibbonButton
            // 
            this.crmWorkspaceRibbonButton.AccessibleDescription = "Open the CRM workspace";
            this.crmWorkspaceRibbonButton.DisplayStyle = Telerik.WinControls.DisplayStyle.ImageAndText;
            this.crmWorkspaceRibbonButton.Image = ((System.Drawing.Image)(resources.GetObject("crmWorkspaceRibbonButton.Image")));
            this.crmWorkspaceRibbonButton.ImageAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.crmWorkspaceRibbonButton.MaxSize = new System.Drawing.Size(112, 86);
            this.crmWorkspaceRibbonButton.MinSize = new System.Drawing.Size(104, 80);
            this.crmWorkspaceRibbonButton.Name = "crmWorkspaceRibbonButton";
            this.crmWorkspaceRibbonButton.Padding = new System.Windows.Forms.Padding(3);
            this.crmWorkspaceRibbonButton.Text = "CRM workspace";
            this.crmWorkspaceRibbonButton.TextAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.crmWorkspaceRibbonButton.TextImageRelation = System.Windows.Forms.TextImageRelation.ImageAboveText;
            this.crmWorkspaceRibbonButton.TextWrap = true;
            this.crmWorkspaceRibbonButton.ToolTipText = "CRM workspace";
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.crmWorkspaceRibbonButton.GetChildAt(1).GetChildAt(1))).AutoEllipsis = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.crmWorkspaceRibbonButton.GetChildAt(1).GetChildAt(1))).TextWrap = true;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.crmWorkspaceRibbonButton.GetChildAt(1).GetChildAt(1))).UseMnemonic = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.crmWorkspaceRibbonButton.GetChildAt(1).GetChildAt(1))).Alignment = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // companiesRibbonButton
            // 
            this.companiesRibbonButton.AccessibleDescription = "Manage companies, accounts and profiles";
            this.companiesRibbonButton.DisplayStyle = Telerik.WinControls.DisplayStyle.ImageAndText;
            this.companiesRibbonButton.Image = ((System.Drawing.Image)(resources.GetObject("companiesRibbonButton.Image")));
            this.companiesRibbonButton.ImageAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.companiesRibbonButton.MaxSize = new System.Drawing.Size(112, 86);
            this.companiesRibbonButton.MinSize = new System.Drawing.Size(104, 80);
            this.companiesRibbonButton.Name = "companiesRibbonButton";
            this.companiesRibbonButton.Padding = new System.Windows.Forms.Padding(3);
            this.companiesRibbonButton.Text = "Companies";
            this.companiesRibbonButton.TextAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.companiesRibbonButton.TextImageRelation = System.Windows.Forms.TextImageRelation.ImageAboveText;
            this.companiesRibbonButton.TextWrap = true;
            this.companiesRibbonButton.ToolTipText = "Companies";
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.companiesRibbonButton.GetChildAt(1).GetChildAt(1))).AutoEllipsis = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.companiesRibbonButton.GetChildAt(1).GetChildAt(1))).TextWrap = true;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.companiesRibbonButton.GetChildAt(1).GetChildAt(1))).UseMnemonic = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.companiesRibbonButton.GetChildAt(1).GetChildAt(1))).Alignment = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // contactsRibbonButton
            // 
            this.contactsRibbonButton.AccessibleDescription = "Manage contacts and relationships";
            this.contactsRibbonButton.DisplayStyle = Telerik.WinControls.DisplayStyle.ImageAndText;
            this.contactsRibbonButton.Image = ((System.Drawing.Image)(resources.GetObject("contactsRibbonButton.Image")));
            this.contactsRibbonButton.ImageAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.contactsRibbonButton.MaxSize = new System.Drawing.Size(112, 86);
            this.contactsRibbonButton.MinSize = new System.Drawing.Size(104, 80);
            this.contactsRibbonButton.Name = "contactsRibbonButton";
            this.contactsRibbonButton.Padding = new System.Windows.Forms.Padding(3);
            this.contactsRibbonButton.Text = "Contacts";
            this.contactsRibbonButton.TextAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.contactsRibbonButton.TextImageRelation = System.Windows.Forms.TextImageRelation.ImageAboveText;
            this.contactsRibbonButton.TextWrap = true;
            this.contactsRibbonButton.ToolTipText = "Contacts";
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.contactsRibbonButton.GetChildAt(1).GetChildAt(1))).AutoEllipsis = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.contactsRibbonButton.GetChildAt(1).GetChildAt(1))).TextWrap = true;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.contactsRibbonButton.GetChildAt(1).GetChildAt(1))).UseMnemonic = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.contactsRibbonButton.GetChildAt(1).GetChildAt(1))).Alignment = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // crmPipelineGroup
            // 
            this.crmPipelineGroup.Items.AddRange(new Telerik.WinControls.RadItem[] {
            this.leadsRibbonButton,
            this.dealsRibbonButton});
            this.crmPipelineGroup.Name = "crmPipelineGroup";
            this.crmPipelineGroup.Text = "Sales pipeline";
            // 
            // leadsRibbonButton
            // 
            this.leadsRibbonButton.AccessibleDescription = "Capture and track leads";
            this.leadsRibbonButton.DisplayStyle = Telerik.WinControls.DisplayStyle.ImageAndText;
            this.leadsRibbonButton.Image = ((System.Drawing.Image)(resources.GetObject("leadsRibbonButton.Image")));
            this.leadsRibbonButton.ImageAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.leadsRibbonButton.MaxSize = new System.Drawing.Size(112, 86);
            this.leadsRibbonButton.MinSize = new System.Drawing.Size(104, 80);
            this.leadsRibbonButton.Name = "leadsRibbonButton";
            this.leadsRibbonButton.Padding = new System.Windows.Forms.Padding(3);
            this.leadsRibbonButton.Text = "Leads";
            this.leadsRibbonButton.TextAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.leadsRibbonButton.TextImageRelation = System.Windows.Forms.TextImageRelation.ImageAboveText;
            this.leadsRibbonButton.TextWrap = true;
            this.leadsRibbonButton.ToolTipText = "Leads";
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.leadsRibbonButton.GetChildAt(1).GetChildAt(1))).AutoEllipsis = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.leadsRibbonButton.GetChildAt(1).GetChildAt(1))).TextWrap = true;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.leadsRibbonButton.GetChildAt(1).GetChildAt(1))).UseMnemonic = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.leadsRibbonButton.GetChildAt(1).GetChildAt(1))).Alignment = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // dealsRibbonButton
            // 
            this.dealsRibbonButton.AccessibleDescription = "Manage sales opportunities";
            this.dealsRibbonButton.DisplayStyle = Telerik.WinControls.DisplayStyle.ImageAndText;
            this.dealsRibbonButton.Image = ((System.Drawing.Image)(resources.GetObject("dealsRibbonButton.Image")));
            this.dealsRibbonButton.ImageAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.dealsRibbonButton.MaxSize = new System.Drawing.Size(112, 86);
            this.dealsRibbonButton.MinSize = new System.Drawing.Size(104, 80);
            this.dealsRibbonButton.Name = "dealsRibbonButton";
            this.dealsRibbonButton.Padding = new System.Windows.Forms.Padding(3);
            this.dealsRibbonButton.Text = "Deals";
            this.dealsRibbonButton.TextAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.dealsRibbonButton.TextImageRelation = System.Windows.Forms.TextImageRelation.ImageAboveText;
            this.dealsRibbonButton.TextWrap = true;
            this.dealsRibbonButton.ToolTipText = "Deals";
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.dealsRibbonButton.GetChildAt(1).GetChildAt(1))).AutoEllipsis = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.dealsRibbonButton.GetChildAt(1).GetChildAt(1))).TextWrap = true;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.dealsRibbonButton.GetChildAt(1).GetChildAt(1))).UseMnemonic = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.dealsRibbonButton.GetChildAt(1).GetChildAt(1))).Alignment = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // financeTab
            // 
            this.financeTab.Items.AddRange(new Telerik.WinControls.RadItem[] {
            this.financeGroup});
            this.financeTab.Name = "financeTab";
            this.financeTab.Text = "Finance & Accounting";
            this.financeTab.UseMnemonic = false;
            // 
            // financeGroup
            // 
            this.financeGroup.Items.AddRange(new Telerik.WinControls.RadItem[] {
            this.financeWorkspaceRibbonButton,
            this.financeLedgersRibbonButton,
            this.financeWorkspacesRibbonButton});
            this.financeGroup.Name = "financeGroup";
            this.financeGroup.Text = "Accounting";
            // 
            // financeWorkspaceRibbonButton
            // 
            this.financeWorkspaceRibbonButton.AccessibleDescription = "Open the finance workspace";
            this.financeWorkspaceRibbonButton.DisplayStyle = Telerik.WinControls.DisplayStyle.ImageAndText;
            this.financeWorkspaceRibbonButton.Image = ((System.Drawing.Image)(resources.GetObject("financeWorkspaceRibbonButton.Image")));
            this.financeWorkspaceRibbonButton.ImageAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.financeWorkspaceRibbonButton.MaxSize = new System.Drawing.Size(112, 86);
            this.financeWorkspaceRibbonButton.MinSize = new System.Drawing.Size(104, 80);
            this.financeWorkspaceRibbonButton.Name = "financeWorkspaceRibbonButton";
            this.financeWorkspaceRibbonButton.Padding = new System.Windows.Forms.Padding(3);
            this.financeWorkspaceRibbonButton.Text = "Finance\nworkspace";
            this.financeWorkspaceRibbonButton.TextAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.financeWorkspaceRibbonButton.TextImageRelation = System.Windows.Forms.TextImageRelation.ImageAboveText;
            this.financeWorkspaceRibbonButton.TextWrap = true;
            this.financeWorkspaceRibbonButton.ToolTipText = "Finance workspace";
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.financeWorkspaceRibbonButton.GetChildAt(1).GetChildAt(1))).AutoEllipsis = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.financeWorkspaceRibbonButton.GetChildAt(1).GetChildAt(1))).TextWrap = true;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.financeWorkspaceRibbonButton.GetChildAt(1).GetChildAt(1))).UseMnemonic = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.financeWorkspaceRibbonButton.GetChildAt(1).GetChildAt(1))).Alignment = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // financeLedgersRibbonButton
            // 
            this.financeLedgersRibbonButton.AccessibleDescription = "Open accounting ledgers";
            this.financeLedgersRibbonButton.DisplayStyle = Telerik.WinControls.DisplayStyle.ImageAndText;
            this.financeLedgersRibbonButton.Image = ((System.Drawing.Image)(resources.GetObject("financeLedgersRibbonButton.Image")));
            this.financeLedgersRibbonButton.ImageAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.financeLedgersRibbonButton.MaxSize = new System.Drawing.Size(112, 86);
            this.financeLedgersRibbonButton.MinSize = new System.Drawing.Size(104, 80);
            this.financeLedgersRibbonButton.Name = "financeLedgersRibbonButton";
            this.financeLedgersRibbonButton.Padding = new System.Windows.Forms.Padding(3);
            this.financeLedgersRibbonButton.Text = "Ledgers";
            this.financeLedgersRibbonButton.TextAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.financeLedgersRibbonButton.TextImageRelation = System.Windows.Forms.TextImageRelation.ImageAboveText;
            this.financeLedgersRibbonButton.TextWrap = true;
            this.financeLedgersRibbonButton.ToolTipText = "Ledgers";
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.financeLedgersRibbonButton.GetChildAt(1).GetChildAt(1))).AutoEllipsis = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.financeLedgersRibbonButton.GetChildAt(1).GetChildAt(1))).TextWrap = true;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.financeLedgersRibbonButton.GetChildAt(1).GetChildAt(1))).UseMnemonic = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.financeLedgersRibbonButton.GetChildAt(1).GetChildAt(1))).Alignment = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // financeWorkspacesRibbonButton
            // 
            this.financeWorkspacesRibbonButton.AccessibleDescription = "Browse finance workspaces";
            this.financeWorkspacesRibbonButton.DisplayStyle = Telerik.WinControls.DisplayStyle.ImageAndText;
            this.financeWorkspacesRibbonButton.Image = ((System.Drawing.Image)(resources.GetObject("financeWorkspacesRibbonButton.Image")));
            this.financeWorkspacesRibbonButton.ImageAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.financeWorkspacesRibbonButton.MaxSize = new System.Drawing.Size(112, 86);
            this.financeWorkspacesRibbonButton.MinSize = new System.Drawing.Size(104, 80);
            this.financeWorkspacesRibbonButton.Name = "financeWorkspacesRibbonButton";
            this.financeWorkspacesRibbonButton.Padding = new System.Windows.Forms.Padding(3);
            this.financeWorkspacesRibbonButton.Text = "Workspaces";
            this.financeWorkspacesRibbonButton.TextAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.financeWorkspacesRibbonButton.TextImageRelation = System.Windows.Forms.TextImageRelation.ImageAboveText;
            this.financeWorkspacesRibbonButton.TextWrap = true;
            this.financeWorkspacesRibbonButton.ToolTipText = "Workspaces";
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.financeWorkspacesRibbonButton.GetChildAt(1).GetChildAt(1))).AutoEllipsis = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.financeWorkspacesRibbonButton.GetChildAt(1).GetChildAt(1))).TextWrap = true;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.financeWorkspacesRibbonButton.GetChildAt(1).GetChildAt(1))).UseMnemonic = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.financeWorkspacesRibbonButton.GetChildAt(1).GetChildAt(1))).Alignment = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // hrmsTab
            // 
            this.hrmsTab.Items.AddRange(new Telerik.WinControls.RadItem[] {
            this.hrmsGroup});
            this.hrmsTab.Name = "hrmsTab";
            this.hrmsTab.Text = "AI HRMS";
            this.hrmsTab.UseMnemonic = false;
            // 
            // hrmsGroup
            // 
            this.hrmsGroup.Items.AddRange(new Telerik.WinControls.RadItem[] {
            this.hrWorkspaceRibbonButton,
            this.hrWorkspacesRibbonButton});
            this.hrmsGroup.Name = "hrmsGroup";
            this.hrmsGroup.Text = "Human resources";
            // 
            // hrWorkspaceRibbonButton
            // 
            this.hrWorkspaceRibbonButton.AccessibleDescription = "Open the HR workspace";
            this.hrWorkspaceRibbonButton.DisplayStyle = Telerik.WinControls.DisplayStyle.ImageAndText;
            this.hrWorkspaceRibbonButton.Image = ((System.Drawing.Image)(resources.GetObject("hrWorkspaceRibbonButton.Image")));
            this.hrWorkspaceRibbonButton.ImageAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.hrWorkspaceRibbonButton.MaxSize = new System.Drawing.Size(112, 86);
            this.hrWorkspaceRibbonButton.MinSize = new System.Drawing.Size(104, 80);
            this.hrWorkspaceRibbonButton.Name = "hrWorkspaceRibbonButton";
            this.hrWorkspaceRibbonButton.Padding = new System.Windows.Forms.Padding(3);
            this.hrWorkspaceRibbonButton.Text = "HR workspace";
            this.hrWorkspaceRibbonButton.TextAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.hrWorkspaceRibbonButton.TextImageRelation = System.Windows.Forms.TextImageRelation.ImageAboveText;
            this.hrWorkspaceRibbonButton.TextWrap = true;
            this.hrWorkspaceRibbonButton.ToolTipText = "HR workspace";
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.hrWorkspaceRibbonButton.GetChildAt(1).GetChildAt(1))).AutoEllipsis = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.hrWorkspaceRibbonButton.GetChildAt(1).GetChildAt(1))).TextWrap = true;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.hrWorkspaceRibbonButton.GetChildAt(1).GetChildAt(1))).UseMnemonic = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.hrWorkspaceRibbonButton.GetChildAt(1).GetChildAt(1))).Alignment = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // hrWorkspacesRibbonButton
            // 
            this.hrWorkspacesRibbonButton.AccessibleDescription = "Browse HR workspaces";
            this.hrWorkspacesRibbonButton.DisplayStyle = Telerik.WinControls.DisplayStyle.ImageAndText;
            this.hrWorkspacesRibbonButton.Image = ((System.Drawing.Image)(resources.GetObject("hrWorkspacesRibbonButton.Image")));
            this.hrWorkspacesRibbonButton.ImageAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.hrWorkspacesRibbonButton.MaxSize = new System.Drawing.Size(112, 86);
            this.hrWorkspacesRibbonButton.MinSize = new System.Drawing.Size(104, 80);
            this.hrWorkspacesRibbonButton.Name = "hrWorkspacesRibbonButton";
            this.hrWorkspacesRibbonButton.Padding = new System.Windows.Forms.Padding(3);
            this.hrWorkspacesRibbonButton.Text = "Workspaces";
            this.hrWorkspacesRibbonButton.TextAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.hrWorkspacesRibbonButton.TextImageRelation = System.Windows.Forms.TextImageRelation.ImageAboveText;
            this.hrWorkspacesRibbonButton.TextWrap = true;
            this.hrWorkspacesRibbonButton.ToolTipText = "Workspaces";
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.hrWorkspacesRibbonButton.GetChildAt(1).GetChildAt(1))).AutoEllipsis = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.hrWorkspacesRibbonButton.GetChildAt(1).GetChildAt(1))).TextWrap = true;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.hrWorkspacesRibbonButton.GetChildAt(1).GetChildAt(1))).UseMnemonic = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.hrWorkspacesRibbonButton.GetChildAt(1).GetChildAt(1))).Alignment = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // projectsTab
            // 
            this.projectsTab.Items.AddRange(new Telerik.WinControls.RadItem[] {
            this.projectsGroup});
            this.projectsTab.Name = "projectsTab";
            this.projectsTab.Text = "KaryaFlow PMS";
            this.projectsTab.UseMnemonic = false;
            // 
            // projectsGroup
            // 
            this.projectsGroup.Items.AddRange(new Telerik.WinControls.RadItem[] {
            this.projectWorkspaceRibbonButton,
            this.projectWorkspacesRibbonButton,
            this.projectMyWorkRibbonButton});
            this.projectsGroup.Name = "projectsGroup";
            this.projectsGroup.Text = "Projects";
            // 
            // projectWorkspaceRibbonButton
            // 
            this.projectWorkspaceRibbonButton.AccessibleDescription = "Open the project workspace";
            this.projectWorkspaceRibbonButton.DisplayStyle = Telerik.WinControls.DisplayStyle.ImageAndText;
            this.projectWorkspaceRibbonButton.Image = ((System.Drawing.Image)(resources.GetObject("projectWorkspaceRibbonButton.Image")));
            this.projectWorkspaceRibbonButton.ImageAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.projectWorkspaceRibbonButton.MaxSize = new System.Drawing.Size(112, 86);
            this.projectWorkspaceRibbonButton.MinSize = new System.Drawing.Size(104, 80);
            this.projectWorkspaceRibbonButton.Name = "projectWorkspaceRibbonButton";
            this.projectWorkspaceRibbonButton.Padding = new System.Windows.Forms.Padding(3);
            this.projectWorkspaceRibbonButton.Text = "Project\nworkspace";
            this.projectWorkspaceRibbonButton.TextAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.projectWorkspaceRibbonButton.TextImageRelation = System.Windows.Forms.TextImageRelation.ImageAboveText;
            this.projectWorkspaceRibbonButton.TextWrap = true;
            this.projectWorkspaceRibbonButton.ToolTipText = "Project workspace";
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.projectWorkspaceRibbonButton.GetChildAt(1).GetChildAt(1))).AutoEllipsis = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.projectWorkspaceRibbonButton.GetChildAt(1).GetChildAt(1))).TextWrap = true;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.projectWorkspaceRibbonButton.GetChildAt(1).GetChildAt(1))).UseMnemonic = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.projectWorkspaceRibbonButton.GetChildAt(1).GetChildAt(1))).Alignment = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // projectWorkspacesRibbonButton
            // 
            this.projectWorkspacesRibbonButton.AccessibleDescription = "Browse project workspaces";
            this.projectWorkspacesRibbonButton.DisplayStyle = Telerik.WinControls.DisplayStyle.ImageAndText;
            this.projectWorkspacesRibbonButton.Image = ((System.Drawing.Image)(resources.GetObject("projectWorkspacesRibbonButton.Image")));
            this.projectWorkspacesRibbonButton.ImageAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.projectWorkspacesRibbonButton.MaxSize = new System.Drawing.Size(112, 86);
            this.projectWorkspacesRibbonButton.MinSize = new System.Drawing.Size(104, 80);
            this.projectWorkspacesRibbonButton.Name = "projectWorkspacesRibbonButton";
            this.projectWorkspacesRibbonButton.Padding = new System.Windows.Forms.Padding(3);
            this.projectWorkspacesRibbonButton.Text = "Workspaces";
            this.projectWorkspacesRibbonButton.TextAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.projectWorkspacesRibbonButton.TextImageRelation = System.Windows.Forms.TextImageRelation.ImageAboveText;
            this.projectWorkspacesRibbonButton.TextWrap = true;
            this.projectWorkspacesRibbonButton.ToolTipText = "Workspaces";
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.projectWorkspacesRibbonButton.GetChildAt(1).GetChildAt(1))).AutoEllipsis = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.projectWorkspacesRibbonButton.GetChildAt(1).GetChildAt(1))).TextWrap = true;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.projectWorkspacesRibbonButton.GetChildAt(1).GetChildAt(1))).UseMnemonic = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.projectWorkspacesRibbonButton.GetChildAt(1).GetChildAt(1))).Alignment = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // projectMyWorkRibbonButton
            // 
            this.projectMyWorkRibbonButton.AccessibleDescription = "Open your assigned work";
            this.projectMyWorkRibbonButton.DisplayStyle = Telerik.WinControls.DisplayStyle.ImageAndText;
            this.projectMyWorkRibbonButton.Image = ((System.Drawing.Image)(resources.GetObject("projectMyWorkRibbonButton.Image")));
            this.projectMyWorkRibbonButton.ImageAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.projectMyWorkRibbonButton.MaxSize = new System.Drawing.Size(112, 86);
            this.projectMyWorkRibbonButton.MinSize = new System.Drawing.Size(104, 80);
            this.projectMyWorkRibbonButton.Name = "projectMyWorkRibbonButton";
            this.projectMyWorkRibbonButton.Padding = new System.Windows.Forms.Padding(3);
            this.projectMyWorkRibbonButton.Text = "My work";
            this.projectMyWorkRibbonButton.TextAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.projectMyWorkRibbonButton.TextImageRelation = System.Windows.Forms.TextImageRelation.ImageAboveText;
            this.projectMyWorkRibbonButton.TextWrap = true;
            this.projectMyWorkRibbonButton.ToolTipText = "My work";
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.projectMyWorkRibbonButton.GetChildAt(1).GetChildAt(1))).AutoEllipsis = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.projectMyWorkRibbonButton.GetChildAt(1).GetChildAt(1))).TextWrap = true;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.projectMyWorkRibbonButton.GetChildAt(1).GetChildAt(1))).UseMnemonic = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.projectMyWorkRibbonButton.GetChildAt(1).GetChildAt(1))).Alignment = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // salesTab
            // 
            this.salesTab.Items.AddRange(new Telerik.WinControls.RadItem[] {
            this.salesGroup});
            this.salesTab.Name = "salesTab";
            this.salesTab.Text = "Sales & POS";
            this.salesTab.UseMnemonic = false;
            // 
            // salesGroup
            // 
            this.salesGroup.Items.AddRange(new Telerik.WinControls.RadItem[] {
            this.salesWorkspaceRibbonButton,
            this.salesAppointmentsRibbonButton});
            this.salesGroup.Name = "salesGroup";
            this.salesGroup.Text = "Sales operations";
            // 
            // salesWorkspaceRibbonButton
            // 
            this.salesWorkspaceRibbonButton.AccessibleDescription = "Open the sales workspace";
            this.salesWorkspaceRibbonButton.DisplayStyle = Telerik.WinControls.DisplayStyle.ImageAndText;
            this.salesWorkspaceRibbonButton.Image = ((System.Drawing.Image)(resources.GetObject("salesWorkspaceRibbonButton.Image")));
            this.salesWorkspaceRibbonButton.ImageAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.salesWorkspaceRibbonButton.MaxSize = new System.Drawing.Size(112, 86);
            this.salesWorkspaceRibbonButton.MinSize = new System.Drawing.Size(104, 80);
            this.salesWorkspaceRibbonButton.Name = "salesWorkspaceRibbonButton";
            this.salesWorkspaceRibbonButton.Padding = new System.Windows.Forms.Padding(3);
            this.salesWorkspaceRibbonButton.Text = "Sales workspace";
            this.salesWorkspaceRibbonButton.TextAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.salesWorkspaceRibbonButton.TextImageRelation = System.Windows.Forms.TextImageRelation.ImageAboveText;
            this.salesWorkspaceRibbonButton.TextWrap = true;
            this.salesWorkspaceRibbonButton.ToolTipText = "Sales workspace";
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.salesWorkspaceRibbonButton.GetChildAt(1).GetChildAt(1))).AutoEllipsis = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.salesWorkspaceRibbonButton.GetChildAt(1).GetChildAt(1))).TextWrap = true;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.salesWorkspaceRibbonButton.GetChildAt(1).GetChildAt(1))).UseMnemonic = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.salesWorkspaceRibbonButton.GetChildAt(1).GetChildAt(1))).Alignment = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // salesAppointmentsRibbonButton
            // 
            this.salesAppointmentsRibbonButton.AccessibleDescription = "Open sales appointments";
            this.salesAppointmentsRibbonButton.DisplayStyle = Telerik.WinControls.DisplayStyle.ImageAndText;
            this.salesAppointmentsRibbonButton.Image = ((System.Drawing.Image)(resources.GetObject("salesAppointmentsRibbonButton.Image")));
            this.salesAppointmentsRibbonButton.ImageAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.salesAppointmentsRibbonButton.MaxSize = new System.Drawing.Size(112, 86);
            this.salesAppointmentsRibbonButton.MinSize = new System.Drawing.Size(104, 80);
            this.salesAppointmentsRibbonButton.Name = "salesAppointmentsRibbonButton";
            this.salesAppointmentsRibbonButton.Padding = new System.Windows.Forms.Padding(3);
            this.salesAppointmentsRibbonButton.Text = "Appointments";
            this.salesAppointmentsRibbonButton.TextAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.salesAppointmentsRibbonButton.TextImageRelation = System.Windows.Forms.TextImageRelation.ImageAboveText;
            this.salesAppointmentsRibbonButton.TextWrap = true;
            this.salesAppointmentsRibbonButton.ToolTipText = "Appointments";
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.salesAppointmentsRibbonButton.GetChildAt(1).GetChildAt(1))).AutoEllipsis = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.salesAppointmentsRibbonButton.GetChildAt(1).GetChildAt(1))).TextWrap = true;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.salesAppointmentsRibbonButton.GetChildAt(1).GetChildAt(1))).UseMnemonic = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.salesAppointmentsRibbonButton.GetChildAt(1).GetChildAt(1))).Alignment = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // sharedTab
            // 
            this.sharedTab.Items.AddRange(new Telerik.WinControls.RadItem[] {
            this.sharedGroup});
            this.sharedTab.Name = "sharedTab";
            this.sharedTab.Text = "Shared";
            this.sharedTab.UseMnemonic = false;
            // 
            // sharedGroup
            // 
            this.sharedGroup.Items.AddRange(new Telerik.WinControls.RadItem[] {
            this.sharedDataRibbonButton,
            this.sharedDocumentsRibbonButton});
            this.sharedGroup.Name = "sharedGroup";
            this.sharedGroup.Text = "Shared workspaces";
            // 
            // sharedDataRibbonButton
            // 
            this.sharedDataRibbonButton.AccessibleDescription = "Access shared business records";
            this.sharedDataRibbonButton.DisplayStyle = Telerik.WinControls.DisplayStyle.ImageAndText;
            this.sharedDataRibbonButton.Image = ((System.Drawing.Image)(resources.GetObject("sharedDataRibbonButton.Image")));
            this.sharedDataRibbonButton.ImageAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.sharedDataRibbonButton.MaxSize = new System.Drawing.Size(112, 86);
            this.sharedDataRibbonButton.MinSize = new System.Drawing.Size(104, 80);
            this.sharedDataRibbonButton.Name = "sharedDataRibbonButton";
            this.sharedDataRibbonButton.Padding = new System.Windows.Forms.Padding(3);
            this.sharedDataRibbonButton.Text = "Shared\nBusiness Data";
            this.sharedDataRibbonButton.TextAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.sharedDataRibbonButton.TextImageRelation = System.Windows.Forms.TextImageRelation.ImageAboveText;
            this.sharedDataRibbonButton.TextWrap = true;
            this.sharedDataRibbonButton.ToolTipText = "Shared Business Data";
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.sharedDataRibbonButton.GetChildAt(1).GetChildAt(1))).AutoEllipsis = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.sharedDataRibbonButton.GetChildAt(1).GetChildAt(1))).TextWrap = true;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.sharedDataRibbonButton.GetChildAt(1).GetChildAt(1))).UseMnemonic = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.sharedDataRibbonButton.GetChildAt(1).GetChildAt(1))).Alignment = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // sharedDocumentsRibbonButton
            // 
            this.sharedDocumentsRibbonButton.AccessibleDescription = "Open documents and communication tools";
            this.sharedDocumentsRibbonButton.DisplayStyle = Telerik.WinControls.DisplayStyle.ImageAndText;
            this.sharedDocumentsRibbonButton.Image = ((System.Drawing.Image)(resources.GetObject("sharedDocumentsRibbonButton.Image")));
            this.sharedDocumentsRibbonButton.ImageAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.sharedDocumentsRibbonButton.MaxSize = new System.Drawing.Size(112, 86);
            this.sharedDocumentsRibbonButton.MinSize = new System.Drawing.Size(104, 80);
            this.sharedDocumentsRibbonButton.Name = "sharedDocumentsRibbonButton";
            this.sharedDocumentsRibbonButton.Padding = new System.Windows.Forms.Padding(3);
            this.sharedDocumentsRibbonButton.Text = "Documents &\nCommunication";
            this.sharedDocumentsRibbonButton.TextAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.sharedDocumentsRibbonButton.TextImageRelation = System.Windows.Forms.TextImageRelation.ImageAboveText;
            this.sharedDocumentsRibbonButton.TextWrap = true;
            this.sharedDocumentsRibbonButton.ToolTipText = "Documents & Communication";
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.sharedDocumentsRibbonButton.GetChildAt(1).GetChildAt(1))).AutoEllipsis = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.sharedDocumentsRibbonButton.GetChildAt(1).GetChildAt(1))).TextWrap = true;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.sharedDocumentsRibbonButton.GetChildAt(1).GetChildAt(1))).UseMnemonic = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.sharedDocumentsRibbonButton.GetChildAt(1).GetChildAt(1))).Alignment = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // administrationTab
            // 
            this.administrationTab.Items.AddRange(new Telerik.WinControls.RadItem[] {
            this.companyGroup});
            this.administrationTab.Name = "administrationTab";
            this.administrationTab.Text = "Administration";
            this.administrationTab.UseMnemonic = false;
            // 
            // companyGroup
            // 
            this.companyGroup.Items.AddRange(new Telerik.WinControls.RadItem[] {
            this.administrationAdministrationRibbonButton,
            this.administrationLocalCompaniesRibbonButton});
            this.companyGroup.Name = "companyGroup";
            this.companyGroup.Text = "Company";
            // 
            // administrationAdministrationRibbonButton
            // 
            this.administrationAdministrationRibbonButton.AccessibleDescription = "Manage company settings and users";
            this.administrationAdministrationRibbonButton.DisplayStyle = Telerik.WinControls.DisplayStyle.ImageAndText;
            this.administrationAdministrationRibbonButton.Image = ((System.Drawing.Image)(resources.GetObject("administrationAdministrationRibbonButton.Image")));
            this.administrationAdministrationRibbonButton.ImageAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.administrationAdministrationRibbonButton.MaxSize = new System.Drawing.Size(112, 86);
            this.administrationAdministrationRibbonButton.MinSize = new System.Drawing.Size(104, 80);
            this.administrationAdministrationRibbonButton.Name = "administrationAdministrationRibbonButton";
            this.administrationAdministrationRibbonButton.Padding = new System.Windows.Forms.Padding(3);
            this.administrationAdministrationRibbonButton.Text = "Company\nAdministration";
            this.administrationAdministrationRibbonButton.TextAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.administrationAdministrationRibbonButton.TextImageRelation = System.Windows.Forms.TextImageRelation.ImageAboveText;
            this.administrationAdministrationRibbonButton.TextWrap = true;
            this.administrationAdministrationRibbonButton.ToolTipText = "Company Administration";
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.administrationAdministrationRibbonButton.GetChildAt(1).GetChildAt(1))).AutoEllipsis = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.administrationAdministrationRibbonButton.GetChildAt(1).GetChildAt(1))).TextWrap = true;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.administrationAdministrationRibbonButton.GetChildAt(1).GetChildAt(1))).UseMnemonic = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.administrationAdministrationRibbonButton.GetChildAt(1).GetChildAt(1))).Alignment = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // administrationLocalCompaniesRibbonButton
            // 
            this.administrationLocalCompaniesRibbonButton.AccessibleDescription = "View and manage local companies";
            this.administrationLocalCompaniesRibbonButton.DisplayStyle = Telerik.WinControls.DisplayStyle.ImageAndText;
            this.administrationLocalCompaniesRibbonButton.Image = ((System.Drawing.Image)(resources.GetObject("administrationLocalCompaniesRibbonButton.Image")));
            this.administrationLocalCompaniesRibbonButton.ImageAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.administrationLocalCompaniesRibbonButton.MaxSize = new System.Drawing.Size(112, 86);
            this.administrationLocalCompaniesRibbonButton.MinSize = new System.Drawing.Size(104, 80);
            this.administrationLocalCompaniesRibbonButton.Name = "administrationLocalCompaniesRibbonButton";
            this.administrationLocalCompaniesRibbonButton.Padding = new System.Windows.Forms.Padding(3);
            this.administrationLocalCompaniesRibbonButton.Text = "Local Companies";
            this.administrationLocalCompaniesRibbonButton.TextAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.administrationLocalCompaniesRibbonButton.TextImageRelation = System.Windows.Forms.TextImageRelation.ImageAboveText;
            this.administrationLocalCompaniesRibbonButton.TextWrap = true;
            this.administrationLocalCompaniesRibbonButton.ToolTipText = "Local Companies";
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.administrationLocalCompaniesRibbonButton.GetChildAt(1).GetChildAt(1))).AutoEllipsis = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.administrationLocalCompaniesRibbonButton.GetChildAt(1).GetChildAt(1))).TextWrap = true;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.administrationLocalCompaniesRibbonButton.GetChildAt(1).GetChildAt(1))).UseMnemonic = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.administrationLocalCompaniesRibbonButton.GetChildAt(1).GetChildAt(1))).Alignment = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // toolsTab
            // 
            this.toolsTab.Items.AddRange(new Telerik.WinControls.RadItem[] {
            this.toolsGroup});
            this.toolsTab.Name = "toolsTab";
            this.toolsTab.Text = "Tools";
            this.toolsTab.UseMnemonic = false;
            // 
            // toolsGroup
            // 
            this.toolsGroup.Items.AddRange(new Telerik.WinControls.RadItem[] {
            this.toolsSettingsRibbonButton,
            this.toolsPowerRibbonButton});
            this.toolsGroup.Name = "toolsGroup";
            this.toolsGroup.Text = "Tools";
            // 
            // toolsSettingsRibbonButton
            // 
            this.toolsSettingsRibbonButton.AccessibleDescription = "Configure the desktop connection";
            this.toolsSettingsRibbonButton.DisplayStyle = Telerik.WinControls.DisplayStyle.ImageAndText;
            this.toolsSettingsRibbonButton.Image = ((System.Drawing.Image)(resources.GetObject("toolsSettingsRibbonButton.Image")));
            this.toolsSettingsRibbonButton.ImageAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.toolsSettingsRibbonButton.MaxSize = new System.Drawing.Size(112, 86);
            this.toolsSettingsRibbonButton.MinSize = new System.Drawing.Size(104, 80);
            this.toolsSettingsRibbonButton.Name = "toolsSettingsRibbonButton";
            this.toolsSettingsRibbonButton.Padding = new System.Windows.Forms.Padding(3);
            this.toolsSettingsRibbonButton.Text = "Settings";
            this.toolsSettingsRibbonButton.TextAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.toolsSettingsRibbonButton.TextImageRelation = System.Windows.Forms.TextImageRelation.ImageAboveText;
            this.toolsSettingsRibbonButton.TextWrap = true;
            this.toolsSettingsRibbonButton.ToolTipText = "Settings";
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.toolsSettingsRibbonButton.GetChildAt(1).GetChildAt(1))).AutoEllipsis = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.toolsSettingsRibbonButton.GetChildAt(1).GetChildAt(1))).TextWrap = true;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.toolsSettingsRibbonButton.GetChildAt(1).GetChildAt(1))).UseMnemonic = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.toolsSettingsRibbonButton.GetChildAt(1).GetChildAt(1))).Alignment = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // toolsPowerRibbonButton
            // 
            this.toolsPowerRibbonButton.AccessibleDescription = "Open apps, automations and approvals";
            this.toolsPowerRibbonButton.DisplayStyle = Telerik.WinControls.DisplayStyle.ImageAndText;
            this.toolsPowerRibbonButton.Image = ((System.Drawing.Image)(resources.GetObject("toolsPowerRibbonButton.Image")));
            this.toolsPowerRibbonButton.ImageAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.toolsPowerRibbonButton.MaxSize = new System.Drawing.Size(112, 86);
            this.toolsPowerRibbonButton.MinSize = new System.Drawing.Size(104, 80);
            this.toolsPowerRibbonButton.Name = "toolsPowerRibbonButton";
            this.toolsPowerRibbonButton.Padding = new System.Windows.Forms.Padding(3);
            this.toolsPowerRibbonButton.Text = "Power Apps";
            this.toolsPowerRibbonButton.TextAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.toolsPowerRibbonButton.TextImageRelation = System.Windows.Forms.TextImageRelation.ImageAboveText;
            this.toolsPowerRibbonButton.TextWrap = true;
            this.toolsPowerRibbonButton.ToolTipText = "Power Apps";
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.toolsPowerRibbonButton.GetChildAt(1).GetChildAt(1))).AutoEllipsis = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.toolsPowerRibbonButton.GetChildAt(1).GetChildAt(1))).TextWrap = true;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.toolsPowerRibbonButton.GetChildAt(1).GetChildAt(1))).UseMnemonic = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.toolsPowerRibbonButton.GetChildAt(1).GetChildAt(1))).Alignment = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // reportsTab
            // 
            this.reportsTab.Items.AddRange(new Telerik.WinControls.RadItem[] {
            this.reportingGroup});
            this.reportsTab.Name = "reportsTab";
            this.reportsTab.Text = "Reports";
            this.reportsTab.UseMnemonic = false;
            // 
            // reportingGroup
            // 
            this.reportingGroup.Items.AddRange(new Telerik.WinControls.RadItem[] {
            this.reportsReportingRibbonButton});
            this.reportingGroup.Name = "reportingGroup";
            this.reportingGroup.Text = "Reporting";
            // 
            // reportsReportingRibbonButton
            // 
            this.reportsReportingRibbonButton.AccessibleDescription = "Open reports and customization tools";
            this.reportsReportingRibbonButton.DisplayStyle = Telerik.WinControls.DisplayStyle.ImageAndText;
            this.reportsReportingRibbonButton.Image = ((System.Drawing.Image)(resources.GetObject("reportsReportingRibbonButton.Image")));
            this.reportsReportingRibbonButton.ImageAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.reportsReportingRibbonButton.MaxSize = new System.Drawing.Size(112, 86);
            this.reportsReportingRibbonButton.MinSize = new System.Drawing.Size(104, 80);
            this.reportsReportingRibbonButton.Name = "reportsReportingRibbonButton";
            this.reportsReportingRibbonButton.Padding = new System.Windows.Forms.Padding(3);
            this.reportsReportingRibbonButton.Text = "Reporting &\nCustomization";
            this.reportsReportingRibbonButton.TextAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.reportsReportingRibbonButton.TextImageRelation = System.Windows.Forms.TextImageRelation.ImageAboveText;
            this.reportsReportingRibbonButton.TextWrap = true;
            this.reportsReportingRibbonButton.ToolTipText = "Reporting & Customization";
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.reportsReportingRibbonButton.GetChildAt(1).GetChildAt(1))).AutoEllipsis = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.reportsReportingRibbonButton.GetChildAt(1).GetChildAt(1))).TextWrap = true;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.reportsReportingRibbonButton.GetChildAt(1).GetChildAt(1))).UseMnemonic = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.reportsReportingRibbonButton.GetChildAt(1).GetChildAt(1))).Alignment = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // helpTab
            // 
            this.helpTab.Items.AddRange(new Telerik.WinControls.RadItem[] {
            this.helpGroup});
            this.helpTab.Name = "helpTab";
            this.helpTab.Text = "Help";
            this.helpTab.UseMnemonic = false;
            // 
            // helpGroup
            // 
            this.helpGroup.Items.AddRange(new Telerik.WinControls.RadItem[] {
            this.helpHelpRibbonButton});
            this.helpGroup.Name = "helpGroup";
            this.helpGroup.Text = "Help";
            // 
            // helpHelpRibbonButton
            // 
            this.helpHelpRibbonButton.AccessibleDescription = "Learn how to open workspaces";
            this.helpHelpRibbonButton.DisplayStyle = Telerik.WinControls.DisplayStyle.ImageAndText;
            this.helpHelpRibbonButton.Image = ((System.Drawing.Image)(resources.GetObject("helpHelpRibbonButton.Image")));
            this.helpHelpRibbonButton.ImageAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.helpHelpRibbonButton.MaxSize = new System.Drawing.Size(112, 86);
            this.helpHelpRibbonButton.MinSize = new System.Drawing.Size(104, 80);
            this.helpHelpRibbonButton.Name = "helpHelpRibbonButton";
            this.helpHelpRibbonButton.Padding = new System.Windows.Forms.Padding(3);
            this.helpHelpRibbonButton.Text = "Navigation Help";
            this.helpHelpRibbonButton.TextAlignment = System.Drawing.ContentAlignment.MiddleCenter;
            this.helpHelpRibbonButton.TextImageRelation = System.Windows.Forms.TextImageRelation.ImageAboveText;
            this.helpHelpRibbonButton.TextWrap = true;
            this.helpHelpRibbonButton.ToolTipText = "Navigation Help";
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.helpHelpRibbonButton.GetChildAt(1).GetChildAt(1))).AutoEllipsis = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.helpHelpRibbonButton.GetChildAt(1).GetChildAt(1))).TextWrap = true;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.helpHelpRibbonButton.GetChildAt(1).GetChildAt(1))).UseMnemonic = false;
            ((Telerik.WinControls.Primitives.TextPrimitive)(this.helpHelpRibbonButton.GetChildAt(1).GetChildAt(1))).Alignment = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // workspaces
            // 
            this.workspaces.Controls.Add(this.homePage);
            this.workspaces.Controls.Add(this.appointmentsPage);
            this.workspaces.Controls.Add(this.crmPage);
            this.workspaces.Controls.Add(this.financePage);
            this.workspaces.Controls.Add(this.hrmsPage);
            this.workspaces.Controls.Add(this.projectsPage);
            this.workspaces.Controls.Add(this.salesPage);
            this.workspaces.Dock = System.Windows.Forms.DockStyle.Fill;
            this.workspaces.Location = new System.Drawing.Point(0, 146);
            this.workspaces.Name = "workspaces";
            this.workspaces.Padding = new System.Drawing.Point(16, 7);
            this.workspaces.SelectedIndex = 0;
            this.workspaces.Size = new System.Drawing.Size(1400, 674);
            this.workspaces.TabIndex = 0;
            // 
            // homePage
            // 
            this.homePage.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.homePage.Controls.Add(this.homeBody);
            this.homePage.Location = new System.Drawing.Point(4, 34);
            this.homePage.Name = "homePage";
            this.homePage.Size = new System.Drawing.Size(1392, 636);
            this.homePage.TabIndex = 0;
            this.homePage.Text = "Home";
            // 
            // homeBody
            // 
            this.homeBody.AutoScroll = true;
            this.homeBody.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.homeBody.Controls.Add(this.homeContent);
            this.homeBody.Dock = System.Windows.Forms.DockStyle.Fill;
            this.homeBody.Location = new System.Drawing.Point(0, 0);
            this.homeBody.Name = "homeBody";
            this.homeBody.Padding = new System.Windows.Forms.Padding(22, 0, 22, 24);
            this.homeBody.Size = new System.Drawing.Size(1392, 636);
            this.homeBody.TabIndex = 0;
            // 
            // homeContent
            // 
            this.homeContent.AutoSize = true;
            this.homeContent.AutoSizeMode = System.Windows.Forms.AutoSizeMode.GrowAndShrink;
            this.homeContent.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.homeContent.Controls.Add(this.sharedCards);
            this.homeContent.Controls.Add(this.sharedHeadingLabel);
            this.homeContent.Controls.Add(this.modulesCards);
            this.homeContent.Controls.Add(this.modulesHeadingLabel);
            this.homeContent.Controls.Add(this.homeHeader);
            this.homeContent.Dock = System.Windows.Forms.DockStyle.Top;
            this.homeContent.Location = new System.Drawing.Point(22, 0);
            this.homeContent.Name = "homeContent";
            this.homeContent.Size = new System.Drawing.Size(1348, 586);
            this.homeContent.TabIndex = 0;
            // 
            // sharedCards
            // 
            this.sharedCards.AutoSize = true;
            this.sharedCards.AutoSizeMode = System.Windows.Forms.AutoSizeMode.GrowAndShrink;
            this.sharedCards.Controls.Add(this.dataCard);
            this.sharedCards.Controls.Add(this.administrationCard);
            this.sharedCards.Controls.Add(this.documentsCard);
            this.sharedCards.Controls.Add(this.powerCard);
            this.sharedCards.Controls.Add(this.reportingCard);
            this.sharedCards.Controls.Add(this.localCompaniesCard);
            this.sharedCards.Dock = System.Windows.Forms.DockStyle.Top;
            this.sharedCards.Location = new System.Drawing.Point(0, 404);
            this.sharedCards.Name = "sharedCards";
            this.sharedCards.Size = new System.Drawing.Size(1348, 182);
            this.sharedCards.TabIndex = 0;
            // 
            // dataCard
            // 
            this.dataCard.AccentColor = System.Drawing.Color.FromArgb(((int)(((byte)(16)))), ((int)(((byte)(132)))), ((int)(((byte)(244)))));
            this.dataCard.AccessibleDescription = "Access shared business records";
            this.dataCard.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.dataCard.Cursor = System.Windows.Forms.Cursors.Hand;
            this.dataCard.FlatStyle = System.Windows.Forms.FlatStyle.Flat;
            this.dataCard.Font = new System.Drawing.Font("Segoe UI", 13F, System.Drawing.FontStyle.Bold);
            this.dataCard.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(24)))), ((int)(((byte)(36)))), ((int)(((byte)(57)))));
            this.dataCard.Location = new System.Drawing.Point(0, 0);
            this.dataCard.Margin = new System.Windows.Forms.Padding(0, 0, 16, 16);
            this.dataCard.Name = "dataCard";
            this.dataCard.Size = new System.Drawing.Size(203, 166);
            this.dataCard.TabIndex = 0;
            this.dataCard.Text = "Shared Business Data";
            this.dataCard.UseVisualStyleBackColor = false;
            // 
            // administrationCard
            // 
            this.administrationCard.AccentColor = System.Drawing.Color.FromArgb(((int)(((byte)(12)))), ((int)(((byte)(183)))), ((int)(((byte)(146)))));
            this.administrationCard.AccessibleDescription = "Manage company settings and users";
            this.administrationCard.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.administrationCard.Cursor = System.Windows.Forms.Cursors.Hand;
            this.administrationCard.FlatStyle = System.Windows.Forms.FlatStyle.Flat;
            this.administrationCard.Font = new System.Drawing.Font("Segoe UI", 13F, System.Drawing.FontStyle.Bold);
            this.administrationCard.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(24)))), ((int)(((byte)(36)))), ((int)(((byte)(57)))));
            this.administrationCard.Location = new System.Drawing.Point(219, 0);
            this.administrationCard.Margin = new System.Windows.Forms.Padding(0, 0, 16, 16);
            this.administrationCard.Name = "administrationCard";
            this.administrationCard.Size = new System.Drawing.Size(203, 166);
            this.administrationCard.TabIndex = 1;
            this.administrationCard.Text = "Company Administration";
            this.administrationCard.UseVisualStyleBackColor = false;
            // 
            // documentsCard
            // 
            this.documentsCard.AccentColor = System.Drawing.Color.FromArgb(((int)(((byte)(247)))), ((int)(((byte)(161)))), ((int)(((byte)(30)))));
            this.documentsCard.AccessibleDescription = "Open documents and communication tools";
            this.documentsCard.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.documentsCard.Cursor = System.Windows.Forms.Cursors.Hand;
            this.documentsCard.FlatStyle = System.Windows.Forms.FlatStyle.Flat;
            this.documentsCard.Font = new System.Drawing.Font("Segoe UI", 13F, System.Drawing.FontStyle.Bold);
            this.documentsCard.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(24)))), ((int)(((byte)(36)))), ((int)(((byte)(57)))));
            this.documentsCard.Location = new System.Drawing.Point(438, 0);
            this.documentsCard.Margin = new System.Windows.Forms.Padding(0, 0, 16, 16);
            this.documentsCard.Name = "documentsCard";
            this.documentsCard.Size = new System.Drawing.Size(203, 166);
            this.documentsCard.TabIndex = 2;
            this.documentsCard.Text = "Documents & Communication";
            this.documentsCard.UseVisualStyleBackColor = false;
            // 
            // powerCard
            // 
            this.powerCard.AccentColor = System.Drawing.Color.FromArgb(((int)(((byte)(143)))), ((int)(((byte)(72)))), ((int)(((byte)(237)))));
            this.powerCard.AccessibleDescription = "Open apps, automations and approvals";
            this.powerCard.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.powerCard.Cursor = System.Windows.Forms.Cursors.Hand;
            this.powerCard.FlatStyle = System.Windows.Forms.FlatStyle.Flat;
            this.powerCard.Font = new System.Drawing.Font("Segoe UI", 13F, System.Drawing.FontStyle.Bold);
            this.powerCard.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(24)))), ((int)(((byte)(36)))), ((int)(((byte)(57)))));
            this.powerCard.Location = new System.Drawing.Point(657, 0);
            this.powerCard.Margin = new System.Windows.Forms.Padding(0, 0, 16, 16);
            this.powerCard.Name = "powerCard";
            this.powerCard.Size = new System.Drawing.Size(203, 166);
            this.powerCard.TabIndex = 3;
            this.powerCard.Text = "Power Apps";
            this.powerCard.UseVisualStyleBackColor = false;
            // 
            // reportingCard
            // 
            this.reportingCard.AccentColor = System.Drawing.Color.FromArgb(((int)(((byte)(10)))), ((int)(((byte)(157)))), ((int)(((byte)(233)))));
            this.reportingCard.AccessibleDescription = "Open reports and customization tools";
            this.reportingCard.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.reportingCard.Cursor = System.Windows.Forms.Cursors.Hand;
            this.reportingCard.FlatStyle = System.Windows.Forms.FlatStyle.Flat;
            this.reportingCard.Font = new System.Drawing.Font("Segoe UI", 13F, System.Drawing.FontStyle.Bold);
            this.reportingCard.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(24)))), ((int)(((byte)(36)))), ((int)(((byte)(57)))));
            this.reportingCard.Location = new System.Drawing.Point(876, 0);
            this.reportingCard.Margin = new System.Windows.Forms.Padding(0, 0, 16, 16);
            this.reportingCard.Name = "reportingCard";
            this.reportingCard.Size = new System.Drawing.Size(203, 166);
            this.reportingCard.TabIndex = 4;
            this.reportingCard.Text = "Reporting & Customization";
            this.reportingCard.UseVisualStyleBackColor = false;
            // 
            // localCompaniesCard
            // 
            this.localCompaniesCard.AccentColor = System.Drawing.Color.FromArgb(((int)(((byte)(16)))), ((int)(((byte)(132)))), ((int)(((byte)(244)))));
            this.localCompaniesCard.AccessibleDescription = "View and manage local companies";
            this.localCompaniesCard.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.localCompaniesCard.Cursor = System.Windows.Forms.Cursors.Hand;
            this.localCompaniesCard.FlatStyle = System.Windows.Forms.FlatStyle.Flat;
            this.localCompaniesCard.Font = new System.Drawing.Font("Segoe UI", 13F, System.Drawing.FontStyle.Bold);
            this.localCompaniesCard.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(24)))), ((int)(((byte)(36)))), ((int)(((byte)(57)))));
            this.localCompaniesCard.Location = new System.Drawing.Point(1095, 0);
            this.localCompaniesCard.Margin = new System.Windows.Forms.Padding(0, 0, 16, 16);
            this.localCompaniesCard.Name = "localCompaniesCard";
            this.localCompaniesCard.Size = new System.Drawing.Size(203, 166);
            this.localCompaniesCard.TabIndex = 5;
            this.localCompaniesCard.Text = "Local Companies";
            this.localCompaniesCard.UseVisualStyleBackColor = false;
            // 
            // sharedHeadingLabel
            // 
            this.sharedHeadingLabel.Dock = System.Windows.Forms.DockStyle.Top;
            this.sharedHeadingLabel.Font = new System.Drawing.Font("Segoe UI", 13F, System.Drawing.FontStyle.Bold);
            this.sharedHeadingLabel.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(61)))), ((int)(((byte)(82)))), ((int)(((byte)(113)))));
            this.sharedHeadingLabel.Location = new System.Drawing.Point(0, 368);
            this.sharedHeadingLabel.Name = "sharedHeadingLabel";
            this.sharedHeadingLabel.Size = new System.Drawing.Size(1348, 36);
            this.sharedHeadingLabel.TabIndex = 1;
            this.sharedHeadingLabel.Text = "Shared";
            this.sharedHeadingLabel.TextAlign = System.Drawing.ContentAlignment.MiddleLeft;
            // 
            // modulesCards
            // 
            this.modulesCards.AutoSize = true;
            this.modulesCards.AutoSizeMode = System.Windows.Forms.AutoSizeMode.GrowAndShrink;
            this.modulesCards.Controls.Add(this.appointmentsCard);
            this.modulesCards.Controls.Add(this.crmCard);
            this.modulesCards.Controls.Add(this.financeCard);
            this.modulesCards.Controls.Add(this.hrmsCard);
            this.modulesCards.Controls.Add(this.projectsCard);
            this.modulesCards.Controls.Add(this.salesCard);
            this.modulesCards.Dock = System.Windows.Forms.DockStyle.Top;
            this.modulesCards.Location = new System.Drawing.Point(0, 186);
            this.modulesCards.Name = "modulesCards";
            this.modulesCards.Size = new System.Drawing.Size(1348, 182);
            this.modulesCards.TabIndex = 2;
            // 
            // appointmentsCard
            // 
            this.appointmentsCard.AccentColor = System.Drawing.Color.FromArgb(((int)(((byte)(16)))), ((int)(((byte)(132)))), ((int)(((byte)(244)))));
            this.appointmentsCard.AccessibleDescription = "Schedule and manage appointments";
            this.appointmentsCard.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.appointmentsCard.Cursor = System.Windows.Forms.Cursors.Hand;
            this.appointmentsCard.FlatStyle = System.Windows.Forms.FlatStyle.Flat;
            this.appointmentsCard.Font = new System.Drawing.Font("Segoe UI", 13F, System.Drawing.FontStyle.Bold);
            this.appointmentsCard.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(24)))), ((int)(((byte)(36)))), ((int)(((byte)(57)))));
            this.appointmentsCard.Location = new System.Drawing.Point(0, 0);
            this.appointmentsCard.Margin = new System.Windows.Forms.Padding(0, 0, 16, 16);
            this.appointmentsCard.Name = "appointmentsCard";
            this.appointmentsCard.Size = new System.Drawing.Size(203, 166);
            this.appointmentsCard.TabIndex = 0;
            this.appointmentsCard.Text = "Appointments";
            this.appointmentsCard.UseVisualStyleBackColor = false;
            // 
            // crmCard
            // 
            this.crmCard.AccentColor = System.Drawing.Color.FromArgb(((int)(((byte)(12)))), ((int)(((byte)(183)))), ((int)(((byte)(146)))));
            this.crmCard.AccessibleDescription = "Manage customer relationships and sales";
            this.crmCard.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.crmCard.Cursor = System.Windows.Forms.Cursors.Hand;
            this.crmCard.FlatStyle = System.Windows.Forms.FlatStyle.Flat;
            this.crmCard.Font = new System.Drawing.Font("Segoe UI", 13F, System.Drawing.FontStyle.Bold);
            this.crmCard.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(24)))), ((int)(((byte)(36)))), ((int)(((byte)(57)))));
            this.crmCard.Location = new System.Drawing.Point(219, 0);
            this.crmCard.Margin = new System.Windows.Forms.Padding(0, 0, 16, 16);
            this.crmCard.Name = "crmCard";
            this.crmCard.Size = new System.Drawing.Size(203, 166);
            this.crmCard.TabIndex = 1;
            this.crmCard.Text = "VyaparaCRM";
            this.crmCard.UseVisualStyleBackColor = false;
            // 
            // financeCard
            // 
            this.financeCard.AccentColor = System.Drawing.Color.FromArgb(((int)(((byte)(247)))), ((int)(((byte)(161)))), ((int)(((byte)(30)))));
            this.financeCard.AccessibleDescription = "Open finance and accounting tools";
            this.financeCard.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.financeCard.Cursor = System.Windows.Forms.Cursors.Hand;
            this.financeCard.FlatStyle = System.Windows.Forms.FlatStyle.Flat;
            this.financeCard.Font = new System.Drawing.Font("Segoe UI", 13F, System.Drawing.FontStyle.Bold);
            this.financeCard.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(24)))), ((int)(((byte)(36)))), ((int)(((byte)(57)))));
            this.financeCard.Location = new System.Drawing.Point(438, 0);
            this.financeCard.Margin = new System.Windows.Forms.Padding(0, 0, 16, 16);
            this.financeCard.Name = "financeCard";
            this.financeCard.Size = new System.Drawing.Size(203, 166);
            this.financeCard.TabIndex = 2;
            this.financeCard.Text = "Finance & Accounting";
            this.financeCard.UseVisualStyleBackColor = false;
            // 
            // hrmsCard
            // 
            this.hrmsCard.AccentColor = System.Drawing.Color.FromArgb(((int)(((byte)(143)))), ((int)(((byte)(72)))), ((int)(((byte)(237)))));
            this.hrmsCard.AccessibleDescription = "Open human resources tools";
            this.hrmsCard.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.hrmsCard.Cursor = System.Windows.Forms.Cursors.Hand;
            this.hrmsCard.FlatStyle = System.Windows.Forms.FlatStyle.Flat;
            this.hrmsCard.Font = new System.Drawing.Font("Segoe UI", 13F, System.Drawing.FontStyle.Bold);
            this.hrmsCard.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(24)))), ((int)(((byte)(36)))), ((int)(((byte)(57)))));
            this.hrmsCard.Location = new System.Drawing.Point(657, 0);
            this.hrmsCard.Margin = new System.Windows.Forms.Padding(0, 0, 16, 16);
            this.hrmsCard.Name = "hrmsCard";
            this.hrmsCard.Size = new System.Drawing.Size(203, 166);
            this.hrmsCard.TabIndex = 3;
            this.hrmsCard.Text = "AI HRMS";
            this.hrmsCard.UseVisualStyleBackColor = false;
            // 
            // projectsCard
            // 
            this.projectsCard.AccentColor = System.Drawing.Color.FromArgb(((int)(((byte)(10)))), ((int)(((byte)(157)))), ((int)(((byte)(233)))));
            this.projectsCard.AccessibleDescription = "Manage projects and workspaces";
            this.projectsCard.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.projectsCard.Cursor = System.Windows.Forms.Cursors.Hand;
            this.projectsCard.FlatStyle = System.Windows.Forms.FlatStyle.Flat;
            this.projectsCard.Font = new System.Drawing.Font("Segoe UI", 13F, System.Drawing.FontStyle.Bold);
            this.projectsCard.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(24)))), ((int)(((byte)(36)))), ((int)(((byte)(57)))));
            this.projectsCard.Location = new System.Drawing.Point(876, 0);
            this.projectsCard.Margin = new System.Windows.Forms.Padding(0, 0, 16, 16);
            this.projectsCard.Name = "projectsCard";
            this.projectsCard.Size = new System.Drawing.Size(203, 166);
            this.projectsCard.TabIndex = 4;
            this.projectsCard.Text = "KaryaFlow PMS";
            this.projectsCard.UseVisualStyleBackColor = false;
            // 
            // salesCard
            // 
            this.salesCard.AccentColor = System.Drawing.Color.FromArgb(((int)(((byte)(16)))), ((int)(((byte)(132)))), ((int)(((byte)(244)))));
            this.salesCard.AccessibleDescription = "Open sales and point of sale tools";
            this.salesCard.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.salesCard.Cursor = System.Windows.Forms.Cursors.Hand;
            this.salesCard.FlatStyle = System.Windows.Forms.FlatStyle.Flat;
            this.salesCard.Font = new System.Drawing.Font("Segoe UI", 13F, System.Drawing.FontStyle.Bold);
            this.salesCard.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(24)))), ((int)(((byte)(36)))), ((int)(((byte)(57)))));
            this.salesCard.Location = new System.Drawing.Point(1095, 0);
            this.salesCard.Margin = new System.Windows.Forms.Padding(0, 0, 16, 16);
            this.salesCard.Name = "salesCard";
            this.salesCard.Size = new System.Drawing.Size(203, 166);
            this.salesCard.TabIndex = 5;
            this.salesCard.Text = "Sales & POS";
            this.salesCard.UseVisualStyleBackColor = false;
            // 
            // modulesHeadingLabel
            // 
            this.modulesHeadingLabel.Dock = System.Windows.Forms.DockStyle.Top;
            this.modulesHeadingLabel.Font = new System.Drawing.Font("Segoe UI", 13F, System.Drawing.FontStyle.Bold);
            this.modulesHeadingLabel.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(61)))), ((int)(((byte)(82)))), ((int)(((byte)(113)))));
            this.modulesHeadingLabel.Location = new System.Drawing.Point(0, 150);
            this.modulesHeadingLabel.Name = "modulesHeadingLabel";
            this.modulesHeadingLabel.Size = new System.Drawing.Size(1348, 36);
            this.modulesHeadingLabel.TabIndex = 3;
            this.modulesHeadingLabel.Text = "Modules";
            this.modulesHeadingLabel.TextAlign = System.Drawing.ContentAlignment.MiddleLeft;
            // 
            // homeHeader
            // 
            this.homeHeader.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.homeHeader.Controls.Add(this.homeTitleLabel);
            this.homeHeader.Controls.Add(this.homeDescriptionLabel);
            this.homeHeader.Dock = System.Windows.Forms.DockStyle.Top;
            this.homeHeader.Location = new System.Drawing.Point(0, 0);
            this.homeHeader.Name = "homeHeader";
            this.homeHeader.Size = new System.Drawing.Size(1348, 150);
            this.homeHeader.TabIndex = 4;
            // 
            // homeTitleLabel
            // 
            this.homeTitleLabel.AutoSize = true;
            this.homeTitleLabel.BackColor = System.Drawing.Color.Transparent;
            this.homeTitleLabel.Font = new System.Drawing.Font("Segoe UI", 30F, System.Drawing.FontStyle.Bold);
            this.homeTitleLabel.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(24)))), ((int)(((byte)(36)))), ((int)(((byte)(57)))));
            this.homeTitleLabel.Location = new System.Drawing.Point(12, 33);
            this.homeTitleLabel.Name = "homeTitleLabel";
            this.homeTitleLabel.Size = new System.Drawing.Size(290, 54);
            this.homeTitleLabel.TabIndex = 0;
            this.homeTitleLabel.Text = "Business Suite";
            // 
            // homeDescriptionLabel
            // 
            this.homeDescriptionLabel.AutoSize = true;
            this.homeDescriptionLabel.BackColor = System.Drawing.Color.Transparent;
            this.homeDescriptionLabel.Font = new System.Drawing.Font("Segoe UI", 11F);
            this.homeDescriptionLabel.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(61)))), ((int)(((byte)(82)))), ((int)(((byte)(113)))));
            this.homeDescriptionLabel.Location = new System.Drawing.Point(15, 91);
            this.homeDescriptionLabel.Name = "homeDescriptionLabel";
            this.homeDescriptionLabel.Size = new System.Drawing.Size(255, 20);
            this.homeDescriptionLabel.TabIndex = 1;
            this.homeDescriptionLabel.Text = "Open a module or shared workspace.";
            // 
            // appointmentsPage
            // 
            this.appointmentsPage.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.appointmentsPage.Controls.Add(this.appointmentsBody);
            this.appointmentsPage.Location = new System.Drawing.Point(4, 34);
            this.appointmentsPage.Name = "appointmentsPage";
            this.appointmentsPage.Size = new System.Drawing.Size(192, 62);
            this.appointmentsPage.TabIndex = 1;
            this.appointmentsPage.Text = "Appointments";
            // 
            // appointmentsBody
            // 
            this.appointmentsBody.AutoScroll = true;
            this.appointmentsBody.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.appointmentsBody.Controls.Add(this.appointmentsContent);
            this.appointmentsBody.Dock = System.Windows.Forms.DockStyle.Fill;
            this.appointmentsBody.Location = new System.Drawing.Point(0, 0);
            this.appointmentsBody.Name = "appointmentsBody";
            this.appointmentsBody.Padding = new System.Windows.Forms.Padding(22, 0, 22, 24);
            this.appointmentsBody.Size = new System.Drawing.Size(192, 62);
            this.appointmentsBody.TabIndex = 0;
            // 
            // appointmentsContent
            // 
            this.appointmentsContent.AutoSize = true;
            this.appointmentsContent.AutoSizeMode = System.Windows.Forms.AutoSizeMode.GrowAndShrink;
            this.appointmentsContent.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.appointmentsContent.Controls.Add(this.appointmentsCards);
            this.appointmentsContent.Controls.Add(this.appointmentsHeader);
            this.appointmentsContent.Dock = System.Windows.Forms.DockStyle.Top;
            this.appointmentsContent.Location = new System.Drawing.Point(22, 0);
            this.appointmentsContent.Name = "appointmentsContent";
            this.appointmentsContent.Size = new System.Drawing.Size(131, 392);
            this.appointmentsContent.TabIndex = 0;
            // 
            // appointmentsCards
            // 
            this.appointmentsCards.AutoSize = true;
            this.appointmentsCards.AutoSizeMode = System.Windows.Forms.AutoSizeMode.GrowAndShrink;
            this.appointmentsCards.Controls.Add(this.appointmentSchedulerCard);
            this.appointmentsCards.Dock = System.Windows.Forms.DockStyle.Top;
            this.appointmentsCards.Location = new System.Drawing.Point(0, 150);
            this.appointmentsCards.Name = "appointmentsCards";
            this.appointmentsCards.Size = new System.Drawing.Size(131, 242);
            this.appointmentsCards.TabIndex = 0;
            // 
            // appointmentSchedulerCard
            // 
            this.appointmentSchedulerCard.AccentColor = System.Drawing.Color.FromArgb(((int)(((byte)(16)))), ((int)(((byte)(132)))), ((int)(((byte)(244)))));
            this.appointmentSchedulerCard.AccessibleDescription = "View and schedule customer appointments.";
            this.appointmentSchedulerCard.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.appointmentSchedulerCard.Cursor = System.Windows.Forms.Cursors.Hand;
            this.appointmentSchedulerCard.FlatStyle = System.Windows.Forms.FlatStyle.Flat;
            this.appointmentSchedulerCard.Font = new System.Drawing.Font("Segoe UI", 13F, System.Drawing.FontStyle.Bold);
            this.appointmentSchedulerCard.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(24)))), ((int)(((byte)(36)))), ((int)(((byte)(57)))));
            this.appointmentSchedulerCard.Location = new System.Drawing.Point(0, 0);
            this.appointmentSchedulerCard.Margin = new System.Windows.Forms.Padding(0, 0, 16, 16);
            this.appointmentSchedulerCard.Name = "appointmentSchedulerCard";
            this.appointmentSchedulerCard.Size = new System.Drawing.Size(246, 226);
            this.appointmentSchedulerCard.TabIndex = 0;
            this.appointmentSchedulerCard.Text = "Appointment scheduler";
            this.appointmentSchedulerCard.UseVisualStyleBackColor = false;
            // 
            // appointmentsHeader
            // 
            this.appointmentsHeader.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.appointmentsHeader.Controls.Add(this.appointmentsHeaderIcon);
            this.appointmentsHeader.Controls.Add(this.appointmentsTitleLabel);
            this.appointmentsHeader.Controls.Add(this.appointmentsDescriptionLabel);
            this.appointmentsHeader.Dock = System.Windows.Forms.DockStyle.Top;
            this.appointmentsHeader.Location = new System.Drawing.Point(0, 0);
            this.appointmentsHeader.Name = "appointmentsHeader";
            this.appointmentsHeader.Size = new System.Drawing.Size(131, 150);
            this.appointmentsHeader.TabIndex = 1;
            // 
            // appointmentsHeaderIcon
            // 
            this.appointmentsHeaderIcon.BackColor = System.Drawing.Color.Transparent;
            this.appointmentsHeaderIcon.Location = new System.Drawing.Point(12, 28);
            this.appointmentsHeaderIcon.Name = "appointmentsHeaderIcon";
            this.appointmentsHeaderIcon.Size = new System.Drawing.Size(88, 88);
            this.appointmentsHeaderIcon.SizeMode = System.Windows.Forms.PictureBoxSizeMode.Zoom;
            this.appointmentsHeaderIcon.TabIndex = 0;
            this.appointmentsHeaderIcon.TabStop = false;
            // 
            // appointmentsTitleLabel
            // 
            this.appointmentsTitleLabel.AutoSize = true;
            this.appointmentsTitleLabel.BackColor = System.Drawing.Color.Transparent;
            this.appointmentsTitleLabel.Font = new System.Drawing.Font("Segoe UI", 30F, System.Drawing.FontStyle.Bold);
            this.appointmentsTitleLabel.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(24)))), ((int)(((byte)(36)))), ((int)(((byte)(57)))));
            this.appointmentsTitleLabel.Location = new System.Drawing.Point(124, 33);
            this.appointmentsTitleLabel.Name = "appointmentsTitleLabel";
            this.appointmentsTitleLabel.Size = new System.Drawing.Size(293, 54);
            this.appointmentsTitleLabel.TabIndex = 1;
            this.appointmentsTitleLabel.Text = "Appointments";
            // 
            // appointmentsDescriptionLabel
            // 
            this.appointmentsDescriptionLabel.AutoSize = true;
            this.appointmentsDescriptionLabel.BackColor = System.Drawing.Color.Transparent;
            this.appointmentsDescriptionLabel.Font = new System.Drawing.Font("Segoe UI", 11F);
            this.appointmentsDescriptionLabel.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(61)))), ((int)(((byte)(82)))), ((int)(((byte)(113)))));
            this.appointmentsDescriptionLabel.Location = new System.Drawing.Point(127, 91);
            this.appointmentsDescriptionLabel.Name = "appointmentsDescriptionLabel";
            this.appointmentsDescriptionLabel.Size = new System.Drawing.Size(286, 20);
            this.appointmentsDescriptionLabel.TabIndex = 2;
            this.appointmentsDescriptionLabel.Text = "Schedule services and customer bookings.";
            // 
            // crmPage
            // 
            this.crmPage.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.crmPage.Controls.Add(this.crmBody);
            this.crmPage.Location = new System.Drawing.Point(4, 34);
            this.crmPage.Name = "crmPage";
            this.crmPage.Size = new System.Drawing.Size(192, 62);
            this.crmPage.TabIndex = 2;
            this.crmPage.Text = "VyaparaCRM";
            // 
            // crmBody
            // 
            this.crmBody.AutoScroll = true;
            this.crmBody.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.crmBody.Controls.Add(this.crmContent);
            this.crmBody.Dock = System.Windows.Forms.DockStyle.Fill;
            this.crmBody.Location = new System.Drawing.Point(0, 0);
            this.crmBody.Name = "crmBody";
            this.crmBody.Padding = new System.Windows.Forms.Padding(22, 0, 22, 24);
            this.crmBody.Size = new System.Drawing.Size(192, 62);
            this.crmBody.TabIndex = 0;
            // 
            // crmContent
            // 
            this.crmContent.AutoSize = true;
            this.crmContent.AutoSizeMode = System.Windows.Forms.AutoSizeMode.GrowAndShrink;
            this.crmContent.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.crmContent.Controls.Add(this.crmCards);
            this.crmContent.Controls.Add(this.crmHeader);
            this.crmContent.Dock = System.Windows.Forms.DockStyle.Top;
            this.crmContent.Location = new System.Drawing.Point(22, 0);
            this.crmContent.Name = "crmContent";
            this.crmContent.Size = new System.Drawing.Size(131, 392);
            this.crmContent.TabIndex = 0;
            // 
            // crmCards
            // 
            this.crmCards.AutoSize = true;
            this.crmCards.AutoSizeMode = System.Windows.Forms.AutoSizeMode.GrowAndShrink;
            this.crmCards.Controls.Add(this.crmWorkspaceCard);
            this.crmCards.Controls.Add(this.companiesCard);
            this.crmCards.Controls.Add(this.contactsCard);
            this.crmCards.Controls.Add(this.leadsCard);
            this.crmCards.Controls.Add(this.dealsCard);
            this.crmCards.Dock = System.Windows.Forms.DockStyle.Top;
            this.crmCards.Location = new System.Drawing.Point(0, 150);
            this.crmCards.Name = "crmCards";
            this.crmCards.Size = new System.Drawing.Size(131, 1210);
            this.crmCards.TabIndex = 0;
            // 
            // crmWorkspaceCard
            // 
            this.crmWorkspaceCard.AccentColor = System.Drawing.Color.FromArgb(((int)(((byte)(16)))), ((int)(((byte)(132)))), ((int)(((byte)(244)))));
            this.crmWorkspaceCard.AccessibleDescription = "Your CRM command center with key insights";
            this.crmWorkspaceCard.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.crmWorkspaceCard.Cursor = System.Windows.Forms.Cursors.Hand;
            this.crmWorkspaceCard.FlatStyle = System.Windows.Forms.FlatStyle.Flat;
            this.crmWorkspaceCard.Font = new System.Drawing.Font("Segoe UI", 13F, System.Drawing.FontStyle.Bold);
            this.crmWorkspaceCard.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(24)))), ((int)(((byte)(36)))), ((int)(((byte)(57)))));
            this.crmWorkspaceCard.Location = new System.Drawing.Point(0, 0);
            this.crmWorkspaceCard.Margin = new System.Windows.Forms.Padding(0, 0, 16, 16);
            this.crmWorkspaceCard.Name = "crmWorkspaceCard";
            this.crmWorkspaceCard.Size = new System.Drawing.Size(246, 226);
            this.crmWorkspaceCard.TabIndex = 0;
            this.crmWorkspaceCard.Text = "CRM workspace";
            this.crmWorkspaceCard.UseVisualStyleBackColor = false;
            // 
            // companiesCard
            // 
            this.companiesCard.AccentColor = System.Drawing.Color.FromArgb(((int)(((byte)(12)))), ((int)(((byte)(183)))), ((int)(((byte)(146)))));
            this.companiesCard.AccessibleDescription = "Manage companies, accounts and profiles";
            this.companiesCard.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.companiesCard.Cursor = System.Windows.Forms.Cursors.Hand;
            this.companiesCard.FlatStyle = System.Windows.Forms.FlatStyle.Flat;
            this.companiesCard.Font = new System.Drawing.Font("Segoe UI", 13F, System.Drawing.FontStyle.Bold);
            this.companiesCard.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(24)))), ((int)(((byte)(36)))), ((int)(((byte)(57)))));
            this.companiesCard.Location = new System.Drawing.Point(0, 242);
            this.companiesCard.Margin = new System.Windows.Forms.Padding(0, 0, 16, 16);
            this.companiesCard.Name = "companiesCard";
            this.companiesCard.Size = new System.Drawing.Size(246, 226);
            this.companiesCard.TabIndex = 1;
            this.companiesCard.Text = "Companies";
            this.companiesCard.UseVisualStyleBackColor = false;
            // 
            // contactsCard
            // 
            this.contactsCard.AccentColor = System.Drawing.Color.FromArgb(((int)(((byte)(247)))), ((int)(((byte)(161)))), ((int)(((byte)(30)))));
            this.contactsCard.AccessibleDescription = "Manage contacts, people and relationships";
            this.contactsCard.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.contactsCard.Cursor = System.Windows.Forms.Cursors.Hand;
            this.contactsCard.FlatStyle = System.Windows.Forms.FlatStyle.Flat;
            this.contactsCard.Font = new System.Drawing.Font("Segoe UI", 13F, System.Drawing.FontStyle.Bold);
            this.contactsCard.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(24)))), ((int)(((byte)(36)))), ((int)(((byte)(57)))));
            this.contactsCard.Location = new System.Drawing.Point(0, 484);
            this.contactsCard.Margin = new System.Windows.Forms.Padding(0, 0, 16, 16);
            this.contactsCard.Name = "contactsCard";
            this.contactsCard.Size = new System.Drawing.Size(246, 226);
            this.contactsCard.TabIndex = 2;
            this.contactsCard.Text = "Contacts";
            this.contactsCard.UseVisualStyleBackColor = false;
            // 
            // leadsCard
            // 
            this.leadsCard.AccentColor = System.Drawing.Color.FromArgb(((int)(((byte)(143)))), ((int)(((byte)(72)))), ((int)(((byte)(237)))));
            this.leadsCard.AccessibleDescription = "Capture, track and nurture potential customers";
            this.leadsCard.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.leadsCard.Cursor = System.Windows.Forms.Cursors.Hand;
            this.leadsCard.FlatStyle = System.Windows.Forms.FlatStyle.Flat;
            this.leadsCard.Font = new System.Drawing.Font("Segoe UI", 13F, System.Drawing.FontStyle.Bold);
            this.leadsCard.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(24)))), ((int)(((byte)(36)))), ((int)(((byte)(57)))));
            this.leadsCard.Location = new System.Drawing.Point(0, 726);
            this.leadsCard.Margin = new System.Windows.Forms.Padding(0, 0, 16, 16);
            this.leadsCard.Name = "leadsCard";
            this.leadsCard.Size = new System.Drawing.Size(246, 226);
            this.leadsCard.TabIndex = 3;
            this.leadsCard.Text = "Leads";
            this.leadsCard.UseVisualStyleBackColor = false;
            // 
            // dealsCard
            // 
            this.dealsCard.AccentColor = System.Drawing.Color.FromArgb(((int)(((byte)(10)))), ((int)(((byte)(157)))), ((int)(((byte)(233)))));
            this.dealsCard.AccessibleDescription = "Manage opportunities and close sales faster";
            this.dealsCard.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.dealsCard.Cursor = System.Windows.Forms.Cursors.Hand;
            this.dealsCard.FlatStyle = System.Windows.Forms.FlatStyle.Flat;
            this.dealsCard.Font = new System.Drawing.Font("Segoe UI", 13F, System.Drawing.FontStyle.Bold);
            this.dealsCard.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(24)))), ((int)(((byte)(36)))), ((int)(((byte)(57)))));
            this.dealsCard.Location = new System.Drawing.Point(0, 968);
            this.dealsCard.Margin = new System.Windows.Forms.Padding(0, 0, 16, 16);
            this.dealsCard.Name = "dealsCard";
            this.dealsCard.Size = new System.Drawing.Size(246, 226);
            this.dealsCard.TabIndex = 4;
            this.dealsCard.Text = "Deals";
            this.dealsCard.UseVisualStyleBackColor = false;
            // 
            // crmHeader
            // 
            this.crmHeader.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.crmHeader.Controls.Add(this.crmHeaderIcon);
            this.crmHeader.Controls.Add(this.crmTitleLabel);
            this.crmHeader.Controls.Add(this.crmDescriptionLabel);
            this.crmHeader.Dock = System.Windows.Forms.DockStyle.Top;
            this.crmHeader.Location = new System.Drawing.Point(0, 0);
            this.crmHeader.Name = "crmHeader";
            this.crmHeader.Size = new System.Drawing.Size(131, 150);
            this.crmHeader.TabIndex = 1;
            // 
            // crmHeaderIcon
            // 
            this.crmHeaderIcon.BackColor = System.Drawing.Color.Transparent;
            this.crmHeaderIcon.Location = new System.Drawing.Point(12, 28);
            this.crmHeaderIcon.Name = "crmHeaderIcon";
            this.crmHeaderIcon.Size = new System.Drawing.Size(88, 88);
            this.crmHeaderIcon.SizeMode = System.Windows.Forms.PictureBoxSizeMode.Zoom;
            this.crmHeaderIcon.TabIndex = 0;
            this.crmHeaderIcon.TabStop = false;
            // 
            // crmTitleLabel
            // 
            this.crmTitleLabel.AutoSize = true;
            this.crmTitleLabel.BackColor = System.Drawing.Color.Transparent;
            this.crmTitleLabel.Font = new System.Drawing.Font("Segoe UI", 30F, System.Drawing.FontStyle.Bold);
            this.crmTitleLabel.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(24)))), ((int)(((byte)(36)))), ((int)(((byte)(57)))));
            this.crmTitleLabel.Location = new System.Drawing.Point(124, 33);
            this.crmTitleLabel.Name = "crmTitleLabel";
            this.crmTitleLabel.Size = new System.Drawing.Size(268, 54);
            this.crmTitleLabel.TabIndex = 1;
            this.crmTitleLabel.Text = "VyaparaCRM";
            // 
            // crmDescriptionLabel
            // 
            this.crmDescriptionLabel.AutoSize = true;
            this.crmDescriptionLabel.BackColor = System.Drawing.Color.Transparent;
            this.crmDescriptionLabel.Font = new System.Drawing.Font("Segoe UI", 11F);
            this.crmDescriptionLabel.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(61)))), ((int)(((byte)(82)))), ((int)(((byte)(113)))));
            this.crmDescriptionLabel.Location = new System.Drawing.Point(127, 91);
            this.crmDescriptionLabel.Name = "crmDescriptionLabel";
            this.crmDescriptionLabel.Size = new System.Drawing.Size(511, 20);
            this.crmDescriptionLabel.TabIndex = 2;
            this.crmDescriptionLabel.Text = "Customer Relationships  •  Sales Pipeline  •  Companies  •  Contacts  •  Deals";
            // 
            // financePage
            // 
            this.financePage.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.financePage.Controls.Add(this.financeBody);
            this.financePage.Location = new System.Drawing.Point(4, 34);
            this.financePage.Name = "financePage";
            this.financePage.Size = new System.Drawing.Size(192, 62);
            this.financePage.TabIndex = 3;
            this.financePage.Text = "Finance & Accounting";
            // 
            // financeBody
            // 
            this.financeBody.AutoScroll = true;
            this.financeBody.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.financeBody.Controls.Add(this.financeContent);
            this.financeBody.Dock = System.Windows.Forms.DockStyle.Fill;
            this.financeBody.Location = new System.Drawing.Point(0, 0);
            this.financeBody.Name = "financeBody";
            this.financeBody.Padding = new System.Windows.Forms.Padding(22, 0, 22, 24);
            this.financeBody.Size = new System.Drawing.Size(192, 62);
            this.financeBody.TabIndex = 0;
            // 
            // financeContent
            // 
            this.financeContent.AutoSize = true;
            this.financeContent.AutoSizeMode = System.Windows.Forms.AutoSizeMode.GrowAndShrink;
            this.financeContent.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.financeContent.Controls.Add(this.financeCards);
            this.financeContent.Controls.Add(this.financeHeader);
            this.financeContent.Dock = System.Windows.Forms.DockStyle.Top;
            this.financeContent.Location = new System.Drawing.Point(22, 0);
            this.financeContent.Name = "financeContent";
            this.financeContent.Size = new System.Drawing.Size(131, 392);
            this.financeContent.TabIndex = 0;
            // 
            // financeCards
            // 
            this.financeCards.AutoSize = true;
            this.financeCards.AutoSizeMode = System.Windows.Forms.AutoSizeMode.GrowAndShrink;
            this.financeCards.Controls.Add(this.financeWorkspaceCard);
            this.financeCards.Controls.Add(this.financeLedgersCard);
            this.financeCards.Controls.Add(this.financeWorkspacesCard);
            this.financeCards.Dock = System.Windows.Forms.DockStyle.Top;
            this.financeCards.Location = new System.Drawing.Point(0, 150);
            this.financeCards.Name = "financeCards";
            this.financeCards.Size = new System.Drawing.Size(131, 726);
            this.financeCards.TabIndex = 0;
            // 
            // financeWorkspaceCard
            // 
            this.financeWorkspaceCard.AccentColor = System.Drawing.Color.FromArgb(((int)(((byte)(16)))), ((int)(((byte)(132)))), ((int)(((byte)(244)))));
            this.financeWorkspaceCard.AccessibleDescription = "Open the finance and accounting workspace.";
            this.financeWorkspaceCard.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.financeWorkspaceCard.Cursor = System.Windows.Forms.Cursors.Hand;
            this.financeWorkspaceCard.FlatStyle = System.Windows.Forms.FlatStyle.Flat;
            this.financeWorkspaceCard.Font = new System.Drawing.Font("Segoe UI", 13F, System.Drawing.FontStyle.Bold);
            this.financeWorkspaceCard.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(24)))), ((int)(((byte)(36)))), ((int)(((byte)(57)))));
            this.financeWorkspaceCard.Location = new System.Drawing.Point(0, 0);
            this.financeWorkspaceCard.Margin = new System.Windows.Forms.Padding(0, 0, 16, 16);
            this.financeWorkspaceCard.Name = "financeWorkspaceCard";
            this.financeWorkspaceCard.Size = new System.Drawing.Size(246, 226);
            this.financeWorkspaceCard.TabIndex = 0;
            this.financeWorkspaceCard.Text = "Finance workspace";
            this.financeWorkspaceCard.UseVisualStyleBackColor = false;
            // 
            // financeLedgersCard
            // 
            this.financeLedgersCard.AccentColor = System.Drawing.Color.FromArgb(((int)(((byte)(12)))), ((int)(((byte)(183)))), ((int)(((byte)(146)))));
            this.financeLedgersCard.AccessibleDescription = "Open accounting ledgers.";
            this.financeLedgersCard.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.financeLedgersCard.Cursor = System.Windows.Forms.Cursors.Hand;
            this.financeLedgersCard.FlatStyle = System.Windows.Forms.FlatStyle.Flat;
            this.financeLedgersCard.Font = new System.Drawing.Font("Segoe UI", 13F, System.Drawing.FontStyle.Bold);
            this.financeLedgersCard.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(24)))), ((int)(((byte)(36)))), ((int)(((byte)(57)))));
            this.financeLedgersCard.Location = new System.Drawing.Point(0, 242);
            this.financeLedgersCard.Margin = new System.Windows.Forms.Padding(0, 0, 16, 16);
            this.financeLedgersCard.Name = "financeLedgersCard";
            this.financeLedgersCard.Size = new System.Drawing.Size(246, 226);
            this.financeLedgersCard.TabIndex = 1;
            this.financeLedgersCard.Text = "Ledgers";
            this.financeLedgersCard.UseVisualStyleBackColor = false;
            // 
            // financeWorkspacesCard
            // 
            this.financeWorkspacesCard.AccentColor = System.Drawing.Color.FromArgb(((int)(((byte)(247)))), ((int)(((byte)(161)))), ((int)(((byte)(30)))));
            this.financeWorkspacesCard.AccessibleDescription = "Browse finance workspaces.";
            this.financeWorkspacesCard.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.financeWorkspacesCard.Cursor = System.Windows.Forms.Cursors.Hand;
            this.financeWorkspacesCard.FlatStyle = System.Windows.Forms.FlatStyle.Flat;
            this.financeWorkspacesCard.Font = new System.Drawing.Font("Segoe UI", 13F, System.Drawing.FontStyle.Bold);
            this.financeWorkspacesCard.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(24)))), ((int)(((byte)(36)))), ((int)(((byte)(57)))));
            this.financeWorkspacesCard.Location = new System.Drawing.Point(0, 484);
            this.financeWorkspacesCard.Margin = new System.Windows.Forms.Padding(0, 0, 16, 16);
            this.financeWorkspacesCard.Name = "financeWorkspacesCard";
            this.financeWorkspacesCard.Size = new System.Drawing.Size(246, 226);
            this.financeWorkspacesCard.TabIndex = 2;
            this.financeWorkspacesCard.Text = "Workspaces";
            this.financeWorkspacesCard.UseVisualStyleBackColor = false;
            // 
            // financeHeader
            // 
            this.financeHeader.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.financeHeader.Controls.Add(this.financeHeaderIcon);
            this.financeHeader.Controls.Add(this.financeTitleLabel);
            this.financeHeader.Controls.Add(this.financeDescriptionLabel);
            this.financeHeader.Dock = System.Windows.Forms.DockStyle.Top;
            this.financeHeader.Location = new System.Drawing.Point(0, 0);
            this.financeHeader.Name = "financeHeader";
            this.financeHeader.Size = new System.Drawing.Size(131, 150);
            this.financeHeader.TabIndex = 1;
            // 
            // financeHeaderIcon
            // 
            this.financeHeaderIcon.BackColor = System.Drawing.Color.Transparent;
            this.financeHeaderIcon.Location = new System.Drawing.Point(12, 28);
            this.financeHeaderIcon.Name = "financeHeaderIcon";
            this.financeHeaderIcon.Size = new System.Drawing.Size(88, 88);
            this.financeHeaderIcon.SizeMode = System.Windows.Forms.PictureBoxSizeMode.Zoom;
            this.financeHeaderIcon.TabIndex = 0;
            this.financeHeaderIcon.TabStop = false;
            // 
            // financeTitleLabel
            // 
            this.financeTitleLabel.AutoSize = true;
            this.financeTitleLabel.BackColor = System.Drawing.Color.Transparent;
            this.financeTitleLabel.Font = new System.Drawing.Font("Segoe UI", 30F, System.Drawing.FontStyle.Bold);
            this.financeTitleLabel.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(24)))), ((int)(((byte)(36)))), ((int)(((byte)(57)))));
            this.financeTitleLabel.Location = new System.Drawing.Point(124, 33);
            this.financeTitleLabel.Name = "financeTitleLabel";
            this.financeTitleLabel.Size = new System.Drawing.Size(402, 54);
            this.financeTitleLabel.TabIndex = 1;
            this.financeTitleLabel.Text = "Finance & Accounting";
            // 
            // financeDescriptionLabel
            // 
            this.financeDescriptionLabel.AutoSize = true;
            this.financeDescriptionLabel.BackColor = System.Drawing.Color.Transparent;
            this.financeDescriptionLabel.Font = new System.Drawing.Font("Segoe UI", 11F);
            this.financeDescriptionLabel.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(61)))), ((int)(((byte)(82)))), ((int)(((byte)(113)))));
            this.financeDescriptionLabel.Location = new System.Drawing.Point(127, 91);
            this.financeDescriptionLabel.Name = "financeDescriptionLabel";
            this.financeDescriptionLabel.Size = new System.Drawing.Size(297, 20);
            this.financeDescriptionLabel.TabIndex = 2;
            this.financeDescriptionLabel.Text = "Accounts, ledgers and financial workspaces.";
            // 
            // hrmsPage
            // 
            this.hrmsPage.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.hrmsPage.Controls.Add(this.hrmsBody);
            this.hrmsPage.Location = new System.Drawing.Point(4, 34);
            this.hrmsPage.Name = "hrmsPage";
            this.hrmsPage.Size = new System.Drawing.Size(192, 62);
            this.hrmsPage.TabIndex = 4;
            this.hrmsPage.Text = "AI HRMS";
            // 
            // hrmsBody
            // 
            this.hrmsBody.AutoScroll = true;
            this.hrmsBody.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.hrmsBody.Controls.Add(this.hrmsContent);
            this.hrmsBody.Dock = System.Windows.Forms.DockStyle.Fill;
            this.hrmsBody.Location = new System.Drawing.Point(0, 0);
            this.hrmsBody.Name = "hrmsBody";
            this.hrmsBody.Padding = new System.Windows.Forms.Padding(22, 0, 22, 24);
            this.hrmsBody.Size = new System.Drawing.Size(192, 62);
            this.hrmsBody.TabIndex = 0;
            // 
            // hrmsContent
            // 
            this.hrmsContent.AutoSize = true;
            this.hrmsContent.AutoSizeMode = System.Windows.Forms.AutoSizeMode.GrowAndShrink;
            this.hrmsContent.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.hrmsContent.Controls.Add(this.hrmsCards);
            this.hrmsContent.Controls.Add(this.hrmsHeader);
            this.hrmsContent.Dock = System.Windows.Forms.DockStyle.Top;
            this.hrmsContent.Location = new System.Drawing.Point(22, 0);
            this.hrmsContent.Name = "hrmsContent";
            this.hrmsContent.Size = new System.Drawing.Size(131, 392);
            this.hrmsContent.TabIndex = 0;
            // 
            // hrmsCards
            // 
            this.hrmsCards.AutoSize = true;
            this.hrmsCards.AutoSizeMode = System.Windows.Forms.AutoSizeMode.GrowAndShrink;
            this.hrmsCards.Controls.Add(this.hrWorkspaceCard);
            this.hrmsCards.Controls.Add(this.hrWorkspacesCard);
            this.hrmsCards.Dock = System.Windows.Forms.DockStyle.Top;
            this.hrmsCards.Location = new System.Drawing.Point(0, 150);
            this.hrmsCards.Name = "hrmsCards";
            this.hrmsCards.Size = new System.Drawing.Size(131, 484);
            this.hrmsCards.TabIndex = 0;
            // 
            // hrWorkspaceCard
            // 
            this.hrWorkspaceCard.AccentColor = System.Drawing.Color.FromArgb(((int)(((byte)(16)))), ((int)(((byte)(132)))), ((int)(((byte)(244)))));
            this.hrWorkspaceCard.AccessibleDescription = "Open the human resources workspace.";
            this.hrWorkspaceCard.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.hrWorkspaceCard.Cursor = System.Windows.Forms.Cursors.Hand;
            this.hrWorkspaceCard.FlatStyle = System.Windows.Forms.FlatStyle.Flat;
            this.hrWorkspaceCard.Font = new System.Drawing.Font("Segoe UI", 13F, System.Drawing.FontStyle.Bold);
            this.hrWorkspaceCard.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(24)))), ((int)(((byte)(36)))), ((int)(((byte)(57)))));
            this.hrWorkspaceCard.Location = new System.Drawing.Point(0, 0);
            this.hrWorkspaceCard.Margin = new System.Windows.Forms.Padding(0, 0, 16, 16);
            this.hrWorkspaceCard.Name = "hrWorkspaceCard";
            this.hrWorkspaceCard.Size = new System.Drawing.Size(246, 226);
            this.hrWorkspaceCard.TabIndex = 0;
            this.hrWorkspaceCard.Text = "HR workspace";
            this.hrWorkspaceCard.UseVisualStyleBackColor = false;
            // 
            // hrWorkspacesCard
            // 
            this.hrWorkspacesCard.AccentColor = System.Drawing.Color.FromArgb(((int)(((byte)(12)))), ((int)(((byte)(183)))), ((int)(((byte)(146)))));
            this.hrWorkspacesCard.AccessibleDescription = "Browse HR workspaces.";
            this.hrWorkspacesCard.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.hrWorkspacesCard.Cursor = System.Windows.Forms.Cursors.Hand;
            this.hrWorkspacesCard.FlatStyle = System.Windows.Forms.FlatStyle.Flat;
            this.hrWorkspacesCard.Font = new System.Drawing.Font("Segoe UI", 13F, System.Drawing.FontStyle.Bold);
            this.hrWorkspacesCard.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(24)))), ((int)(((byte)(36)))), ((int)(((byte)(57)))));
            this.hrWorkspacesCard.Location = new System.Drawing.Point(0, 242);
            this.hrWorkspacesCard.Margin = new System.Windows.Forms.Padding(0, 0, 16, 16);
            this.hrWorkspacesCard.Name = "hrWorkspacesCard";
            this.hrWorkspacesCard.Size = new System.Drawing.Size(246, 226);
            this.hrWorkspacesCard.TabIndex = 1;
            this.hrWorkspacesCard.Text = "Workspaces";
            this.hrWorkspacesCard.UseVisualStyleBackColor = false;
            // 
            // hrmsHeader
            // 
            this.hrmsHeader.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.hrmsHeader.Controls.Add(this.hrmsHeaderIcon);
            this.hrmsHeader.Controls.Add(this.hrmsTitleLabel);
            this.hrmsHeader.Controls.Add(this.hrmsDescriptionLabel);
            this.hrmsHeader.Dock = System.Windows.Forms.DockStyle.Top;
            this.hrmsHeader.Location = new System.Drawing.Point(0, 0);
            this.hrmsHeader.Name = "hrmsHeader";
            this.hrmsHeader.Size = new System.Drawing.Size(131, 150);
            this.hrmsHeader.TabIndex = 1;
            // 
            // hrmsHeaderIcon
            // 
            this.hrmsHeaderIcon.BackColor = System.Drawing.Color.Transparent;
            this.hrmsHeaderIcon.Location = new System.Drawing.Point(12, 28);
            this.hrmsHeaderIcon.Name = "hrmsHeaderIcon";
            this.hrmsHeaderIcon.Size = new System.Drawing.Size(88, 88);
            this.hrmsHeaderIcon.SizeMode = System.Windows.Forms.PictureBoxSizeMode.Zoom;
            this.hrmsHeaderIcon.TabIndex = 0;
            this.hrmsHeaderIcon.TabStop = false;
            // 
            // hrmsTitleLabel
            // 
            this.hrmsTitleLabel.AutoSize = true;
            this.hrmsTitleLabel.BackColor = System.Drawing.Color.Transparent;
            this.hrmsTitleLabel.Font = new System.Drawing.Font("Segoe UI", 30F, System.Drawing.FontStyle.Bold);
            this.hrmsTitleLabel.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(24)))), ((int)(((byte)(36)))), ((int)(((byte)(57)))));
            this.hrmsTitleLabel.Location = new System.Drawing.Point(124, 33);
            this.hrmsTitleLabel.Name = "hrmsTitleLabel";
            this.hrmsTitleLabel.Size = new System.Drawing.Size(192, 54);
            this.hrmsTitleLabel.TabIndex = 1;
            this.hrmsTitleLabel.Text = "AI HRMS";
            // 
            // hrmsDescriptionLabel
            // 
            this.hrmsDescriptionLabel.AutoSize = true;
            this.hrmsDescriptionLabel.BackColor = System.Drawing.Color.Transparent;
            this.hrmsDescriptionLabel.Font = new System.Drawing.Font("Segoe UI", 11F);
            this.hrmsDescriptionLabel.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(61)))), ((int)(((byte)(82)))), ((int)(((byte)(113)))));
            this.hrmsDescriptionLabel.Location = new System.Drawing.Point(127, 91);
            this.hrmsDescriptionLabel.Name = "hrmsDescriptionLabel";
            this.hrmsDescriptionLabel.Size = new System.Drawing.Size(286, 20);
            this.hrmsDescriptionLabel.TabIndex = 2;
            this.hrmsDescriptionLabel.Text = "Employees, attendance, leave and payroll.";
            // 
            // projectsPage
            // 
            this.projectsPage.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.projectsPage.Controls.Add(this.projectsBody);
            this.projectsPage.Location = new System.Drawing.Point(4, 34);
            this.projectsPage.Name = "projectsPage";
            this.projectsPage.Size = new System.Drawing.Size(192, 62);
            this.projectsPage.TabIndex = 5;
            this.projectsPage.Text = "KaryaFlow PMS";
            // 
            // projectsBody
            // 
            this.projectsBody.AutoScroll = true;
            this.projectsBody.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.projectsBody.Controls.Add(this.projectsContent);
            this.projectsBody.Dock = System.Windows.Forms.DockStyle.Fill;
            this.projectsBody.Location = new System.Drawing.Point(0, 0);
            this.projectsBody.Name = "projectsBody";
            this.projectsBody.Padding = new System.Windows.Forms.Padding(22, 0, 22, 24);
            this.projectsBody.Size = new System.Drawing.Size(192, 62);
            this.projectsBody.TabIndex = 0;
            // 
            // projectsContent
            // 
            this.projectsContent.AutoSize = true;
            this.projectsContent.AutoSizeMode = System.Windows.Forms.AutoSizeMode.GrowAndShrink;
            this.projectsContent.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.projectsContent.Controls.Add(this.projectsCards);
            this.projectsContent.Controls.Add(this.projectsHeader);
            this.projectsContent.Dock = System.Windows.Forms.DockStyle.Top;
            this.projectsContent.Location = new System.Drawing.Point(22, 0);
            this.projectsContent.Name = "projectsContent";
            this.projectsContent.Size = new System.Drawing.Size(131, 392);
            this.projectsContent.TabIndex = 0;
            // 
            // projectsCards
            // 
            this.projectsCards.AutoSize = true;
            this.projectsCards.AutoSizeMode = System.Windows.Forms.AutoSizeMode.GrowAndShrink;
            this.projectsCards.Controls.Add(this.projectWorkspaceCard);
            this.projectsCards.Controls.Add(this.projectWorkspacesCard);
            this.projectsCards.Controls.Add(this.projectMyWorkCard);
            this.projectsCards.Dock = System.Windows.Forms.DockStyle.Top;
            this.projectsCards.Location = new System.Drawing.Point(0, 150);
            this.projectsCards.Name = "projectsCards";
            this.projectsCards.Size = new System.Drawing.Size(131, 726);
            this.projectsCards.TabIndex = 0;
            // 
            // projectWorkspaceCard
            // 
            this.projectWorkspaceCard.AccentColor = System.Drawing.Color.FromArgb(((int)(((byte)(16)))), ((int)(((byte)(132)))), ((int)(((byte)(244)))));
            this.projectWorkspaceCard.AccessibleDescription = "Open the project management workspace.";
            this.projectWorkspaceCard.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.projectWorkspaceCard.Cursor = System.Windows.Forms.Cursors.Hand;
            this.projectWorkspaceCard.FlatStyle = System.Windows.Forms.FlatStyle.Flat;
            this.projectWorkspaceCard.Font = new System.Drawing.Font("Segoe UI", 13F, System.Drawing.FontStyle.Bold);
            this.projectWorkspaceCard.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(24)))), ((int)(((byte)(36)))), ((int)(((byte)(57)))));
            this.projectWorkspaceCard.Location = new System.Drawing.Point(0, 0);
            this.projectWorkspaceCard.Margin = new System.Windows.Forms.Padding(0, 0, 16, 16);
            this.projectWorkspaceCard.Name = "projectWorkspaceCard";
            this.projectWorkspaceCard.Size = new System.Drawing.Size(246, 226);
            this.projectWorkspaceCard.TabIndex = 0;
            this.projectWorkspaceCard.Text = "Project workspace";
            this.projectWorkspaceCard.UseVisualStyleBackColor = false;
            // 
            // projectWorkspacesCard
            // 
            this.projectWorkspacesCard.AccentColor = System.Drawing.Color.FromArgb(((int)(((byte)(12)))), ((int)(((byte)(183)))), ((int)(((byte)(146)))));
            this.projectWorkspacesCard.AccessibleDescription = "Browse project workspaces.";
            this.projectWorkspacesCard.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.projectWorkspacesCard.Cursor = System.Windows.Forms.Cursors.Hand;
            this.projectWorkspacesCard.FlatStyle = System.Windows.Forms.FlatStyle.Flat;
            this.projectWorkspacesCard.Font = new System.Drawing.Font("Segoe UI", 13F, System.Drawing.FontStyle.Bold);
            this.projectWorkspacesCard.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(24)))), ((int)(((byte)(36)))), ((int)(((byte)(57)))));
            this.projectWorkspacesCard.Location = new System.Drawing.Point(0, 242);
            this.projectWorkspacesCard.Margin = new System.Windows.Forms.Padding(0, 0, 16, 16);
            this.projectWorkspacesCard.Name = "projectWorkspacesCard";
            this.projectWorkspacesCard.Size = new System.Drawing.Size(246, 226);
            this.projectWorkspacesCard.TabIndex = 1;
            this.projectWorkspacesCard.Text = "Workspaces";
            this.projectWorkspacesCard.UseVisualStyleBackColor = false;
            // 
            // projectMyWorkCard
            // 
            this.projectMyWorkCard.AccentColor = System.Drawing.Color.FromArgb(((int)(((byte)(247)))), ((int)(((byte)(161)))), ((int)(((byte)(30)))));
            this.projectMyWorkCard.AccessibleDescription = "Open your assigned work.";
            this.projectMyWorkCard.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.projectMyWorkCard.Cursor = System.Windows.Forms.Cursors.Hand;
            this.projectMyWorkCard.FlatStyle = System.Windows.Forms.FlatStyle.Flat;
            this.projectMyWorkCard.Font = new System.Drawing.Font("Segoe UI", 13F, System.Drawing.FontStyle.Bold);
            this.projectMyWorkCard.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(24)))), ((int)(((byte)(36)))), ((int)(((byte)(57)))));
            this.projectMyWorkCard.Location = new System.Drawing.Point(0, 484);
            this.projectMyWorkCard.Margin = new System.Windows.Forms.Padding(0, 0, 16, 16);
            this.projectMyWorkCard.Name = "projectMyWorkCard";
            this.projectMyWorkCard.Size = new System.Drawing.Size(246, 226);
            this.projectMyWorkCard.TabIndex = 2;
            this.projectMyWorkCard.Text = "My work";
            this.projectMyWorkCard.UseVisualStyleBackColor = false;
            // 
            // projectsHeader
            // 
            this.projectsHeader.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.projectsHeader.Controls.Add(this.projectsHeaderIcon);
            this.projectsHeader.Controls.Add(this.projectsTitleLabel);
            this.projectsHeader.Controls.Add(this.projectsDescriptionLabel);
            this.projectsHeader.Dock = System.Windows.Forms.DockStyle.Top;
            this.projectsHeader.Location = new System.Drawing.Point(0, 0);
            this.projectsHeader.Name = "projectsHeader";
            this.projectsHeader.Size = new System.Drawing.Size(131, 150);
            this.projectsHeader.TabIndex = 1;
            // 
            // projectsHeaderIcon
            // 
            this.projectsHeaderIcon.BackColor = System.Drawing.Color.Transparent;
            this.projectsHeaderIcon.Location = new System.Drawing.Point(12, 28);
            this.projectsHeaderIcon.Name = "projectsHeaderIcon";
            this.projectsHeaderIcon.Size = new System.Drawing.Size(88, 88);
            this.projectsHeaderIcon.SizeMode = System.Windows.Forms.PictureBoxSizeMode.Zoom;
            this.projectsHeaderIcon.TabIndex = 0;
            this.projectsHeaderIcon.TabStop = false;
            // 
            // projectsTitleLabel
            // 
            this.projectsTitleLabel.AutoSize = true;
            this.projectsTitleLabel.BackColor = System.Drawing.Color.Transparent;
            this.projectsTitleLabel.Font = new System.Drawing.Font("Segoe UI", 30F, System.Drawing.FontStyle.Bold);
            this.projectsTitleLabel.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(24)))), ((int)(((byte)(36)))), ((int)(((byte)(57)))));
            this.projectsTitleLabel.Location = new System.Drawing.Point(124, 33);
            this.projectsTitleLabel.Name = "projectsTitleLabel";
            this.projectsTitleLabel.Size = new System.Drawing.Size(317, 54);
            this.projectsTitleLabel.TabIndex = 1;
            this.projectsTitleLabel.Text = "KaryaFlow PMS";
            // 
            // projectsDescriptionLabel
            // 
            this.projectsDescriptionLabel.AutoSize = true;
            this.projectsDescriptionLabel.BackColor = System.Drawing.Color.Transparent;
            this.projectsDescriptionLabel.Font = new System.Drawing.Font("Segoe UI", 11F);
            this.projectsDescriptionLabel.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(61)))), ((int)(((byte)(82)))), ((int)(((byte)(113)))));
            this.projectsDescriptionLabel.Location = new System.Drawing.Point(127, 91);
            this.projectsDescriptionLabel.Name = "projectsDescriptionLabel";
            this.projectsDescriptionLabel.Size = new System.Drawing.Size(212, 20);
            this.projectsDescriptionLabel.TabIndex = 2;
            this.projectsDescriptionLabel.Text = "Projects, workspaces and tasks.";
            // 
            // salesPage
            // 
            this.salesPage.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.salesPage.Controls.Add(this.salesBody);
            this.salesPage.Location = new System.Drawing.Point(4, 34);
            this.salesPage.Name = "salesPage";
            this.salesPage.Size = new System.Drawing.Size(192, 62);
            this.salesPage.TabIndex = 6;
            this.salesPage.Text = "Sales & POS";
            // 
            // salesBody
            // 
            this.salesBody.AutoScroll = true;
            this.salesBody.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.salesBody.Controls.Add(this.salesContent);
            this.salesBody.Dock = System.Windows.Forms.DockStyle.Fill;
            this.salesBody.Location = new System.Drawing.Point(0, 0);
            this.salesBody.Name = "salesBody";
            this.salesBody.Padding = new System.Windows.Forms.Padding(22, 0, 22, 24);
            this.salesBody.Size = new System.Drawing.Size(192, 62);
            this.salesBody.TabIndex = 0;
            // 
            // salesContent
            // 
            this.salesContent.AutoSize = true;
            this.salesContent.AutoSizeMode = System.Windows.Forms.AutoSizeMode.GrowAndShrink;
            this.salesContent.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.salesContent.Controls.Add(this.salesCards);
            this.salesContent.Controls.Add(this.salesHeader);
            this.salesContent.Dock = System.Windows.Forms.DockStyle.Top;
            this.salesContent.Location = new System.Drawing.Point(22, 0);
            this.salesContent.Name = "salesContent";
            this.salesContent.Size = new System.Drawing.Size(131, 392);
            this.salesContent.TabIndex = 0;
            // 
            // salesCards
            // 
            this.salesCards.AutoSize = true;
            this.salesCards.AutoSizeMode = System.Windows.Forms.AutoSizeMode.GrowAndShrink;
            this.salesCards.Controls.Add(this.salesWorkspaceCard);
            this.salesCards.Controls.Add(this.salesAppointmentsCard);
            this.salesCards.Dock = System.Windows.Forms.DockStyle.Top;
            this.salesCards.Location = new System.Drawing.Point(0, 150);
            this.salesCards.Name = "salesCards";
            this.salesCards.Size = new System.Drawing.Size(131, 484);
            this.salesCards.TabIndex = 0;
            // 
            // salesWorkspaceCard
            // 
            this.salesWorkspaceCard.AccentColor = System.Drawing.Color.FromArgb(((int)(((byte)(16)))), ((int)(((byte)(132)))), ((int)(((byte)(244)))));
            this.salesWorkspaceCard.AccessibleDescription = "Open the sales and point of sale workspace.";
            this.salesWorkspaceCard.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.salesWorkspaceCard.Cursor = System.Windows.Forms.Cursors.Hand;
            this.salesWorkspaceCard.FlatStyle = System.Windows.Forms.FlatStyle.Flat;
            this.salesWorkspaceCard.Font = new System.Drawing.Font("Segoe UI", 13F, System.Drawing.FontStyle.Bold);
            this.salesWorkspaceCard.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(24)))), ((int)(((byte)(36)))), ((int)(((byte)(57)))));
            this.salesWorkspaceCard.Location = new System.Drawing.Point(0, 0);
            this.salesWorkspaceCard.Margin = new System.Windows.Forms.Padding(0, 0, 16, 16);
            this.salesWorkspaceCard.Name = "salesWorkspaceCard";
            this.salesWorkspaceCard.Size = new System.Drawing.Size(246, 226);
            this.salesWorkspaceCard.TabIndex = 0;
            this.salesWorkspaceCard.Text = "Sales workspace";
            this.salesWorkspaceCard.UseVisualStyleBackColor = false;
            // 
            // salesAppointmentsCard
            // 
            this.salesAppointmentsCard.AccentColor = System.Drawing.Color.FromArgb(((int)(((byte)(12)))), ((int)(((byte)(183)))), ((int)(((byte)(146)))));
            this.salesAppointmentsCard.AccessibleDescription = "Open sales appointments.";
            this.salesAppointmentsCard.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.salesAppointmentsCard.Cursor = System.Windows.Forms.Cursors.Hand;
            this.salesAppointmentsCard.FlatStyle = System.Windows.Forms.FlatStyle.Flat;
            this.salesAppointmentsCard.Font = new System.Drawing.Font("Segoe UI", 13F, System.Drawing.FontStyle.Bold);
            this.salesAppointmentsCard.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(24)))), ((int)(((byte)(36)))), ((int)(((byte)(57)))));
            this.salesAppointmentsCard.Location = new System.Drawing.Point(0, 242);
            this.salesAppointmentsCard.Margin = new System.Windows.Forms.Padding(0, 0, 16, 16);
            this.salesAppointmentsCard.Name = "salesAppointmentsCard";
            this.salesAppointmentsCard.Size = new System.Drawing.Size(246, 226);
            this.salesAppointmentsCard.TabIndex = 1;
            this.salesAppointmentsCard.Text = "Appointments";
            this.salesAppointmentsCard.UseVisualStyleBackColor = false;
            // 
            // salesHeader
            // 
            this.salesHeader.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(244)))), ((int)(((byte)(247)))), ((int)(((byte)(253)))));
            this.salesHeader.Controls.Add(this.salesHeaderIcon);
            this.salesHeader.Controls.Add(this.salesTitleLabel);
            this.salesHeader.Controls.Add(this.salesDescriptionLabel);
            this.salesHeader.Dock = System.Windows.Forms.DockStyle.Top;
            this.salesHeader.Location = new System.Drawing.Point(0, 0);
            this.salesHeader.Name = "salesHeader";
            this.salesHeader.Size = new System.Drawing.Size(131, 150);
            this.salesHeader.TabIndex = 1;
            // 
            // salesHeaderIcon
            // 
            this.salesHeaderIcon.BackColor = System.Drawing.Color.Transparent;
            this.salesHeaderIcon.Location = new System.Drawing.Point(12, 28);
            this.salesHeaderIcon.Name = "salesHeaderIcon";
            this.salesHeaderIcon.Size = new System.Drawing.Size(88, 88);
            this.salesHeaderIcon.SizeMode = System.Windows.Forms.PictureBoxSizeMode.Zoom;
            this.salesHeaderIcon.TabIndex = 0;
            this.salesHeaderIcon.TabStop = false;
            // 
            // salesTitleLabel
            // 
            this.salesTitleLabel.AutoSize = true;
            this.salesTitleLabel.BackColor = System.Drawing.Color.Transparent;
            this.salesTitleLabel.Font = new System.Drawing.Font("Segoe UI", 30F, System.Drawing.FontStyle.Bold);
            this.salesTitleLabel.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(24)))), ((int)(((byte)(36)))), ((int)(((byte)(57)))));
            this.salesTitleLabel.Location = new System.Drawing.Point(124, 33);
            this.salesTitleLabel.Name = "salesTitleLabel";
            this.salesTitleLabel.Size = new System.Drawing.Size(217, 54);
            this.salesTitleLabel.TabIndex = 1;
            this.salesTitleLabel.Text = "Sales & POS";
            // 
            // salesDescriptionLabel
            // 
            this.salesDescriptionLabel.AutoSize = true;
            this.salesDescriptionLabel.BackColor = System.Drawing.Color.Transparent;
            this.salesDescriptionLabel.Font = new System.Drawing.Font("Segoe UI", 11F);
            this.salesDescriptionLabel.ForeColor = System.Drawing.Color.FromArgb(((int)(((byte)(61)))), ((int)(((byte)(82)))), ((int)(((byte)(113)))));
            this.salesDescriptionLabel.Location = new System.Drawing.Point(127, 91);
            this.salesDescriptionLabel.Name = "salesDescriptionLabel";
            this.salesDescriptionLabel.Size = new System.Drawing.Size(281, 20);
            this.salesDescriptionLabel.TabIndex = 2;
            this.salesDescriptionLabel.Text = "Sales, checkout and inventory operations.";
            // 
            // MainForm
            // 
            this.AutoScaleDimensions = new System.Drawing.SizeF(96F, 96F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Dpi;
            this.BackColor = System.Drawing.Color.FromArgb(((int)(((byte)(232)))), ((int)(((byte)(239)))), ((int)(((byte)(250)))));
            this.ClientSize = new System.Drawing.Size(1400, 820);
            this.Controls.Add(this.workspaces);
            this.Controls.Add(this.ribbonBar);
            this.Font = new System.Drawing.Font("Segoe UI", 10F);
            this.MinimumSize = new System.Drawing.Size(770, 530);
            this.Name = "MainForm";
            this.StartPosition = System.Windows.Forms.FormStartPosition.CenterScreen;
            this.Text = "Business Suite";
            ((System.ComponentModel.ISupportInitialize)(this.ribbonBar)).EndInit();
            this.workspaces.ResumeLayout(false);
            this.homePage.ResumeLayout(false);
            this.homeBody.ResumeLayout(false);
            this.homeBody.PerformLayout();
            this.homeContent.ResumeLayout(false);
            this.homeContent.PerformLayout();
            this.sharedCards.ResumeLayout(false);
            this.modulesCards.ResumeLayout(false);
            this.homeHeader.ResumeLayout(false);
            this.homeHeader.PerformLayout();
            this.appointmentsPage.ResumeLayout(false);
            this.appointmentsBody.ResumeLayout(false);
            this.appointmentsBody.PerformLayout();
            this.appointmentsContent.ResumeLayout(false);
            this.appointmentsContent.PerformLayout();
            this.appointmentsCards.ResumeLayout(false);
            this.appointmentsHeader.ResumeLayout(false);
            this.appointmentsHeader.PerformLayout();
            ((System.ComponentModel.ISupportInitialize)(this.appointmentsHeaderIcon)).EndInit();
            this.crmPage.ResumeLayout(false);
            this.crmBody.ResumeLayout(false);
            this.crmBody.PerformLayout();
            this.crmContent.ResumeLayout(false);
            this.crmContent.PerformLayout();
            this.crmCards.ResumeLayout(false);
            this.crmHeader.ResumeLayout(false);
            this.crmHeader.PerformLayout();
            ((System.ComponentModel.ISupportInitialize)(this.crmHeaderIcon)).EndInit();
            this.financePage.ResumeLayout(false);
            this.financeBody.ResumeLayout(false);
            this.financeBody.PerformLayout();
            this.financeContent.ResumeLayout(false);
            this.financeContent.PerformLayout();
            this.financeCards.ResumeLayout(false);
            this.financeHeader.ResumeLayout(false);
            this.financeHeader.PerformLayout();
            ((System.ComponentModel.ISupportInitialize)(this.financeHeaderIcon)).EndInit();
            this.hrmsPage.ResumeLayout(false);
            this.hrmsBody.ResumeLayout(false);
            this.hrmsBody.PerformLayout();
            this.hrmsContent.ResumeLayout(false);
            this.hrmsContent.PerformLayout();
            this.hrmsCards.ResumeLayout(false);
            this.hrmsHeader.ResumeLayout(false);
            this.hrmsHeader.PerformLayout();
            ((System.ComponentModel.ISupportInitialize)(this.hrmsHeaderIcon)).EndInit();
            this.projectsPage.ResumeLayout(false);
            this.projectsBody.ResumeLayout(false);
            this.projectsBody.PerformLayout();
            this.projectsContent.ResumeLayout(false);
            this.projectsContent.PerformLayout();
            this.projectsCards.ResumeLayout(false);
            this.projectsHeader.ResumeLayout(false);
            this.projectsHeader.PerformLayout();
            ((System.ComponentModel.ISupportInitialize)(this.projectsHeaderIcon)).EndInit();
            this.salesPage.ResumeLayout(false);
            this.salesBody.ResumeLayout(false);
            this.salesBody.PerformLayout();
            this.salesContent.ResumeLayout(false);
            this.salesContent.PerformLayout();
            this.salesCards.ResumeLayout(false);
            this.salesHeader.ResumeLayout(false);
            this.salesHeader.PerformLayout();
            ((System.ComponentModel.ISupportInitialize)(this.salesHeaderIcon)).EndInit();
            this.workspaces.SelectedIndexChanged += new System.EventHandler(this.workspaces_SelectedIndexChanged);
            this.ribbonBar.CommandTabSelected += new Telerik.WinControls.UI.CommandTabEventHandler(this.ribbonBar_CommandTabSelected);
            this.homeHomeRibbonButton.Click += new System.EventHandler(this.homeButton_Click);
            this.appointmentSchedulerRibbonButton.Click += new System.EventHandler(this.appointmentSchedulerButton_Click);
            this.crmWorkspaceRibbonButton.Click += new System.EventHandler(this.crmWorkspaceButton_Click);
            this.companiesRibbonButton.Click += new System.EventHandler(this.companiesButton_Click);
            this.contactsRibbonButton.Click += new System.EventHandler(this.contactsButton_Click);
            this.leadsRibbonButton.Click += new System.EventHandler(this.leadsButton_Click);
            this.dealsRibbonButton.Click += new System.EventHandler(this.dealsButton_Click);
            this.financeWorkspaceRibbonButton.Click += new System.EventHandler(this.financeWorkspaceButton_Click);
            this.financeLedgersRibbonButton.Click += new System.EventHandler(this.financeLedgersButton_Click);
            this.financeWorkspacesRibbonButton.Click += new System.EventHandler(this.financeWorkspacesButton_Click);
            this.hrWorkspaceRibbonButton.Click += new System.EventHandler(this.hrWorkspaceButton_Click);
            this.hrWorkspacesRibbonButton.Click += new System.EventHandler(this.hrWorkspacesButton_Click);
            this.projectWorkspaceRibbonButton.Click += new System.EventHandler(this.projectWorkspaceButton_Click);
            this.projectWorkspacesRibbonButton.Click += new System.EventHandler(this.projectWorkspacesButton_Click);
            this.projectMyWorkRibbonButton.Click += new System.EventHandler(this.projectMyWorkButton_Click);
            this.salesWorkspaceRibbonButton.Click += new System.EventHandler(this.salesWorkspaceButton_Click);
            this.salesAppointmentsRibbonButton.Click += new System.EventHandler(this.salesAppointmentsButton_Click);
            this.sharedDataRibbonButton.Click += new System.EventHandler(this.dataButton_Click);
            this.sharedDocumentsRibbonButton.Click += new System.EventHandler(this.documentsButton_Click);
            this.administrationAdministrationRibbonButton.Click += new System.EventHandler(this.administrationButton_Click);
            this.administrationLocalCompaniesRibbonButton.Click += new System.EventHandler(this.localCompaniesButton_Click);
            this.toolsSettingsRibbonButton.Click += new System.EventHandler(this.settingsButton_Click);
            this.toolsPowerRibbonButton.Click += new System.EventHandler(this.powerButton_Click);
            this.reportsReportingRibbonButton.Click += new System.EventHandler(this.reportingButton_Click);
            this.helpHelpRibbonButton.Click += new System.EventHandler(this.helpButton_Click);
            this.appointmentsCard.Click += new System.EventHandler(this.appointmentsButton_Click);
            this.crmCard.Click += new System.EventHandler(this.crmButton_Click);
            this.financeCard.Click += new System.EventHandler(this.financeButton_Click);
            this.hrmsCard.Click += new System.EventHandler(this.hrmsButton_Click);
            this.projectsCard.Click += new System.EventHandler(this.projectsButton_Click);
            this.salesCard.Click += new System.EventHandler(this.salesButton_Click);
            this.dataCard.Click += new System.EventHandler(this.dataButton_Click);
            this.administrationCard.Click += new System.EventHandler(this.administrationButton_Click);
            this.documentsCard.Click += new System.EventHandler(this.documentsButton_Click);
            this.powerCard.Click += new System.EventHandler(this.powerButton_Click);
            this.reportingCard.Click += new System.EventHandler(this.reportingButton_Click);
            this.localCompaniesCard.Click += new System.EventHandler(this.localCompaniesButton_Click);
            this.appointmentSchedulerCard.Click += new System.EventHandler(this.appointmentSchedulerButton_Click);
            this.crmWorkspaceCard.Click += new System.EventHandler(this.crmWorkspaceButton_Click);
            this.companiesCard.Click += new System.EventHandler(this.companiesButton_Click);
            this.contactsCard.Click += new System.EventHandler(this.contactsButton_Click);
            this.leadsCard.Click += new System.EventHandler(this.leadsButton_Click);
            this.dealsCard.Click += new System.EventHandler(this.dealsButton_Click);
            this.financeWorkspaceCard.Click += new System.EventHandler(this.financeWorkspaceButton_Click);
            this.financeLedgersCard.Click += new System.EventHandler(this.financeLedgersButton_Click);
            this.financeWorkspacesCard.Click += new System.EventHandler(this.financeWorkspacesButton_Click);
            this.hrWorkspaceCard.Click += new System.EventHandler(this.hrWorkspaceButton_Click);
            this.hrWorkspacesCard.Click += new System.EventHandler(this.hrWorkspacesButton_Click);
            this.projectWorkspaceCard.Click += new System.EventHandler(this.projectWorkspaceButton_Click);
            this.projectWorkspacesCard.Click += new System.EventHandler(this.projectWorkspacesButton_Click);
            this.projectMyWorkCard.Click += new System.EventHandler(this.projectMyWorkButton_Click);
            this.salesWorkspaceCard.Click += new System.EventHandler(this.salesWorkspaceButton_Click);
            this.salesAppointmentsCard.Click += new System.EventHandler(this.salesAppointmentsButton_Click);
            this.ResumeLayout(false);
            this.PerformLayout();

        }

        private RadRibbonBar ribbonBar;
        private RibbonTab homeTab;
        private RadRibbonBarGroup workspaceGroup;
        private RadButtonElement homeHomeRibbonButton;
        private RibbonTab appointmentsTab;
        private RadRibbonBarGroup appointmentsGroup;
        private RadButtonElement appointmentSchedulerRibbonButton;
        private RibbonTab crmTab;
        private RadRibbonBarGroup crmGroup;
        private RadButtonElement crmWorkspaceRibbonButton;
        private RadButtonElement companiesRibbonButton;
        private RadButtonElement contactsRibbonButton;
        private RadRibbonBarGroup crmPipelineGroup;
        private RadButtonElement leadsRibbonButton;
        private RadButtonElement dealsRibbonButton;
        private RibbonTab financeTab;
        private RadRibbonBarGroup financeGroup;
        private RadButtonElement financeWorkspaceRibbonButton;
        private RadButtonElement financeLedgersRibbonButton;
        private RadButtonElement financeWorkspacesRibbonButton;
        private RibbonTab hrmsTab;
        private RadRibbonBarGroup hrmsGroup;
        private RadButtonElement hrWorkspaceRibbonButton;
        private RadButtonElement hrWorkspacesRibbonButton;
        private RibbonTab projectsTab;
        private RadRibbonBarGroup projectsGroup;
        private RadButtonElement projectWorkspaceRibbonButton;
        private RadButtonElement projectWorkspacesRibbonButton;
        private RadButtonElement projectMyWorkRibbonButton;
        private RibbonTab salesTab;
        private RadRibbonBarGroup salesGroup;
        private RadButtonElement salesWorkspaceRibbonButton;
        private RadButtonElement salesAppointmentsRibbonButton;
        private RibbonTab sharedTab;
        private RadRibbonBarGroup sharedGroup;
        private RadButtonElement sharedDataRibbonButton;
        private RadButtonElement sharedDocumentsRibbonButton;
        private RibbonTab administrationTab;
        private RadRibbonBarGroup companyGroup;
        private RadButtonElement administrationAdministrationRibbonButton;
        private RadButtonElement administrationLocalCompaniesRibbonButton;
        private RibbonTab toolsTab;
        private RadRibbonBarGroup toolsGroup;
        private RadButtonElement toolsSettingsRibbonButton;
        private RadButtonElement toolsPowerRibbonButton;
        private RibbonTab reportsTab;
        private RadRibbonBarGroup reportingGroup;
        private RadButtonElement reportsReportingRibbonButton;
        private RibbonTab helpTab;
        private RadRibbonBarGroup helpGroup;
        private RadButtonElement helpHelpRibbonButton;
        private WorkspaceTabControl workspaces;
        private TabPage homePage;
        private Panel homeBody;
        private Panel homeContent;
        private WorkspaceHeader homeHeader;
        private Label homeTitleLabel;
        private Label homeDescriptionLabel;
        private Label modulesHeadingLabel;
        private FlowLayoutPanel modulesCards;
        private WorkspaceCard appointmentsCard;
        private WorkspaceCard crmCard;
        private WorkspaceCard financeCard;
        private WorkspaceCard hrmsCard;
        private WorkspaceCard projectsCard;
        private WorkspaceCard salesCard;
        private Label sharedHeadingLabel;
        private FlowLayoutPanel sharedCards;
        private WorkspaceCard dataCard;
        private WorkspaceCard administrationCard;
        private WorkspaceCard documentsCard;
        private WorkspaceCard powerCard;
        private WorkspaceCard reportingCard;
        private WorkspaceCard localCompaniesCard;
        private TabPage crmPage;
        private Panel crmBody;
        private Panel crmContent;
        private WorkspaceHeader crmHeader;
        private PictureBox crmHeaderIcon;
        private Label crmTitleLabel;
        private Label crmDescriptionLabel;
        private FlowLayoutPanel crmCards;
        private WorkspaceCard crmWorkspaceCard;
        private WorkspaceCard companiesCard;
        private WorkspaceCard contactsCard;
        private WorkspaceCard leadsCard;
        private WorkspaceCard dealsCard;
        private TabPage appointmentsPage;
        private Panel appointmentsBody;
        private Panel appointmentsContent;
        private WorkspaceHeader appointmentsHeader;
        private PictureBox appointmentsHeaderIcon;
        private Label appointmentsTitleLabel;
        private Label appointmentsDescriptionLabel;
        private FlowLayoutPanel appointmentsCards;
        private WorkspaceCard appointmentSchedulerCard;
        private TabPage financePage;
        private Panel financeBody;
        private Panel financeContent;
        private WorkspaceHeader financeHeader;
        private PictureBox financeHeaderIcon;
        private Label financeTitleLabel;
        private Label financeDescriptionLabel;
        private FlowLayoutPanel financeCards;
        private WorkspaceCard financeWorkspaceCard;
        private WorkspaceCard financeLedgersCard;
        private WorkspaceCard financeWorkspacesCard;
        private TabPage hrmsPage;
        private Panel hrmsBody;
        private Panel hrmsContent;
        private WorkspaceHeader hrmsHeader;
        private PictureBox hrmsHeaderIcon;
        private Label hrmsTitleLabel;
        private Label hrmsDescriptionLabel;
        private FlowLayoutPanel hrmsCards;
        private WorkspaceCard hrWorkspaceCard;
        private WorkspaceCard hrWorkspacesCard;
        private TabPage projectsPage;
        private Panel projectsBody;
        private Panel projectsContent;
        private WorkspaceHeader projectsHeader;
        private PictureBox projectsHeaderIcon;
        private Label projectsTitleLabel;
        private Label projectsDescriptionLabel;
        private FlowLayoutPanel projectsCards;
        private WorkspaceCard projectWorkspaceCard;
        private WorkspaceCard projectWorkspacesCard;
        private WorkspaceCard projectMyWorkCard;
        private TabPage salesPage;
        private Panel salesBody;
        private Panel salesContent;
        private WorkspaceHeader salesHeader;
        private PictureBox salesHeaderIcon;
        private Label salesTitleLabel;
        private Label salesDescriptionLabel;
        private FlowLayoutPanel salesCards;
        private WorkspaceCard salesWorkspaceCard;
        private WorkspaceCard salesAppointmentsCard;
    }
}
