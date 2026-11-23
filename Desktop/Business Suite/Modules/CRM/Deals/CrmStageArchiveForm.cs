namespace Business_Suite;

public sealed partial class CrmStageArchiveForm : Form
{
    private readonly bool needsReplacement;

    public CrmStageArchiveForm() => InitializeComponent();

    internal CrmStageArchiveForm(string stage,long assigned,IReadOnlyList<CrmDealStage> targets) : this()
    {
        needsReplacement=assigned>0;
        prompt.Text=needsReplacement
            ?$"Archive {stage} and move its {assigned:N0} assigned Deals to the selected stage."
            :$"Archive {stage}. No Deals are assigned to this stage.";
        targetBox.Visible=targetLabel.Visible=needsReplacement;
        targetBox.DisplayMember=nameof(CrmDealStage.Name);
        targetBox.DataSource=targets;
        targetBox.SelectedIndex=-1;
        if (needsReplacement && targets.Count==0)
            prompt.Text+=" No active replacement with the same outcome is available.";
        SelectionChanged(this,EventArgs.Empty);
    }

    internal int? Replacement {get;private set;}

    private void SelectionChanged(object sender,EventArgs e) =>
        archiveButton.Enabled=!needsReplacement || targetBox.SelectedItem?.DataBoundItem is CrmDealStage;

    private void ArchiveClicked(object sender,EventArgs e)
    {
        if (!archiveButton.Enabled)
            return;
        Replacement=needsReplacement?(targetBox.SelectedItem?.DataBoundItem as CrmDealStage)?.Id:null;
        DialogResult=DialogResult.OK;
    }
}
