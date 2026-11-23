using System.Globalization;

namespace Business_Suite;

public sealed partial class LeadSellerAvailabilityForm : Form
{
    private readonly Dictionary<int,LeadSellerAvailability> policies=new();
    private readonly HashSet<int> configured=new();
    private LeadSalesChoice? current;
    private bool binding;

    public LeadSellerAvailabilityForm() => InitializeComponent();

    internal LeadSellerAvailabilityForm(IEnumerable<LeadSalesChoice> people,IEnumerable<int> owners,
        IEnumerable<LeadSellerAvailability> existing) : this()
    {
        configured.UnionWith(owners);
        foreach (var policy in existing) policies[policy.OwnerId]=policy;
        var names=people.ToDictionary(person=>person.Id);
        var all=configured.Concat(policies.Keys).Distinct().Select(id=>names.TryGetValue(id,out var person)
            ?person:new LeadSalesChoice(id,$"Unavailable user #{id}")).OrderBy(person=>person.Name).ToList();
        ownerBox.DataSource=all;
        saveButton.Enabled=all.Count>0;
        if (all.Count==0) feedback.Text="Add an owner to the routing pool or to a rule first.";
    }

    internal List<LeadSellerAvailability> Policies => policies.Values.ToList();

    private void OwnerChanged(object sender,EventArgs e)
    {
        if (binding || ownerBox.SelectedItem is not LeadSalesChoice next) return;
        if (!SaveCurrent())
        {
            binding=true;
            ownerBox.SelectedItem=current;
            binding=false;
            return;
        }
        current=next;
        bool exists=policies.TryGetValue(next.Id,out var policy);
        policy??=LeadSellerAvailability.Default(next.Id);
        binding=true;
        usePolicy.Checked=exists;
        enabledBox.Checked=policy.Enabled;
        zoneBox.Text=policy.Timezone;
        startBox.Text=LeadSellerAvailability.FormatMinute(policy.StartMinute);
        endBox.Text=LeadSellerAvailability.FormatMinute(policy.EndMinute);
        capacityBox.Text=policy.MaxActiveLeads?.ToString(CultureInfo.InvariantCulture)??"";
        for(int day=0;day<dayList.Items.Count;day++) dayList.SetItemChecked(day,policy.Days.Contains(day));
        binding=false;
        UpdateInputs();
        feedback.Text=configured.Contains(next.Id)?"":"Remove this policy or add its owner back to the routing pool or a rule.";
    }

    private void PolicyChanged(object sender,EventArgs e)
    {
        if (!binding) UpdateInputs();
    }

    private void UpdateInputs()
    {
        usePolicy.Enabled=current is not null;
        details.Enabled=current is not null && usePolicy.Checked;
    }

    private bool SaveCurrent()
    {
        if (current is null) return true;
        if (!usePolicy.Checked)
        {
            policies.Remove(current.Id);
            return true;
        }
        try
        {
            string zone=zoneBox.Text.Trim();
            if (zone.Length==0) throw new ArgumentException("Enter an IANA time zone.");
            int start=LeadSellerAvailability.ParseMinute(startBox.Text,false);
            int end=LeadSellerAvailability.ParseMinute(endBox.Text,true);
            if (start>=end) throw new ArgumentException("The shift end must be after the start.");
            int? capacity=null;
            if (!string.IsNullOrWhiteSpace(capacityBox.Text))
            {
                if (!int.TryParse(capacityBox.Text.Trim(),NumberStyles.None,CultureInfo.InvariantCulture,out int parsed) ||
                    parsed is <1 or >100000)
                    throw new ArgumentException("Use an active Lead limit of 1 to 100,000 or leave it blank.");
                capacity=parsed;
            }
            policies[current.Id]=new(current.Id,enabledBox.Checked,zone,dayList.CheckedIndices.Cast<int>().ToArray(),start,end,capacity);
            return true;
        }
        catch (ArgumentException error)
        {
            feedback.Text=error.Message;
            return false;
        }
    }

    private void SaveClicked(object sender,EventArgs e)
    {
        if (!SaveCurrent()) return;
        DialogResult=DialogResult.OK;
        Close();
    }
}
