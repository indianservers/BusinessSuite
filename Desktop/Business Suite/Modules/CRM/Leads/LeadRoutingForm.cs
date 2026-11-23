using Npgsql;

namespace Business_Suite;

public sealed partial class LeadRoutingForm : Form
{
    private sealed record RuleRow(string Field,string Match,string Owner);
    private readonly CancellationTokenSource lifetime=new();
    private LeadRoutingSettings? current;
    private readonly List<LeadRouteRule> rules=new();
    private List<LeadSellerAvailability> policies=new();
    private bool busy;

    public LeadRoutingForm() => InitializeComponent();

    private async void FormShown(object sender,EventArgs e) => await RunAsync(async token =>
    {
        var settings=await LeadStore.ReadLeadRoutingSettingsAsync(token);
        if (token.IsCancellationRequested) return;
        current=settings;
        policies=settings.Availability;
        modeBox.SelectedIndex=settings.Mode switch {"round_robin"=>1,"workload"=>2,_=>0};
        ownerBox.DataSource=settings.People;
        fieldBox.DataSource=LeadStore.NativeLeadRoutingFields;
        foreach(var person in settings.People.Concat(settings.OwnerIds.Except(settings.People.Select(person=>person.Id))
            .Select(id=>new LeadSalesChoice(id,$"Unavailable user #{id}"))))
            poolList.Items.Add(person,settings.OwnerIds.Contains(person.Id));
        rules.AddRange(settings.Rules);
        BindRules(-1);
        status.Text="";
    });

    private void BindRules(int selection)
    {
        ruleGrid.DataSource=rules.Select(rule=>new RuleRow(rule.Field,rule.EqualsValue,
            current?.People.FirstOrDefault(person=>person.Id==rule.OwnerId)?.Name ?? $"User #{rule.OwnerId}")).ToList();
        ruleGrid.ClearSelection();
        if (selection>=0 && selection<ruleGrid.Rows.Count)
            ruleGrid.CurrentRow=ruleGrid.Rows[selection];
    }

    private void AddClicked(object sender,EventArgs e) => SaveRule(false);
    private void ApplyClicked(object sender,EventArgs e) => SaveRule(true);

    private void SaveRule(bool replace)
    {
        int index=SelectedIndex;
        if (current is null || ownerBox.SelectedItem is not LeadSalesChoice owner || fieldBox.SelectedItem is not string field ||
            string.IsNullOrWhiteSpace(matchBox.Text) || replace && index<0)
        {
            status.Text="Choose a field and owner, then enter the match value.";
            return;
        }
        if (!replace && rules.Count>=100)
        {
            status.Text="Use up to 100 assignment rules.";
            return;
        }
        var rule=new LeadRouteRule(field,matchBox.Text.Trim(),owner.Id);
        if (replace) rules[index]=rule;
        else { index=rules.Count; rules.Add(rule); }
        BindRules(index);
        status.Text="Save settings to apply changes.";
    }

    private int SelectedIndex=>ruleGrid.CurrentRow is {Index:>=0} row && row.Index<rules.Count?row.Index:-1;

    private void GridSelectionChanged(object sender,EventArgs e)
    {
        int index=SelectedIndex;
        if (index<0) return;
        var rule=rules[index];
        fieldBox.SelectedItem=rule.Field;
        matchBox.Text=rule.EqualsValue;
        ownerBox.SelectedIndex=current?.People.FindIndex(person=>person.Id==rule.OwnerId)??-1;
    }

    private void RemoveClicked(object sender,EventArgs e)
    {
        int index=SelectedIndex;
        if (index<0) return;
        rules.RemoveAt(index);
        BindRules(Math.Min(index,rules.Count-1));
    }

    private void EarlierClicked(object sender,EventArgs e) => MoveRule(-1);
    private void LaterClicked(object sender,EventArgs e) => MoveRule(1);

    private void MoveRule(int step)
    {
        int index=SelectedIndex,target=index+step;
        if (index<0 || target<0 || target>=rules.Count) return;
        (rules[index],rules[target])=(rules[target],rules[index]);
        BindRules(target);
    }

    private void AvailabilityClicked(object sender,EventArgs e)
    {
        if (current is null) return;
        var owners=poolList.CheckedItems.Cast<LeadSalesChoice>().Select(owner=>owner.Id).Concat(rules.Select(rule=>rule.OwnerId));
        using var form=new LeadSellerAvailabilityForm(current.People,owners,policies);
        if (form.ShowDialog(this)==DialogResult.OK)
        {
            policies=form.Policies;
            status.Text="Save routing settings to apply working hours and capacity.";
        }
    }

    private async void SaveClicked(object sender,EventArgs e)
    {
        if (current is null) return;
        await RunAsync(async token =>
        {
            var chosen=poolList.CheckedItems.Cast<LeadSalesChoice>().Select(owner=>owner.Id).ToArray();
            var pool=current.OwnerIds.Where(chosen.Contains).Concat(chosen.Where(id=>!current.OwnerIds.Contains(id))).ToArray();
            string mode=modeBox.SelectedIndex switch {1=>"round_robin",2=>"workload",_=>"manual"};
            await LeadStore.SaveLeadRoutingSettingsAsync(current.Revision,mode,pool,rules,token,policies);
            if (token.IsCancellationRequested) return;
            busy=false;
            DialogResult=DialogResult.OK;
            Close();
        });
    }

    private async Task RunAsync(Func<CancellationToken,Task> operation)
    {
        if (busy) return;
        busy=true;
        editor.Enabled=saveButton.Enabled=false;
        var token=lifetime.Token;
        try { await operation(token); }
        catch (OperationCanceledException) when (token.IsCancellationRequested) { }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or IOException or
            ArgumentException or InvalidOperationException or UnauthorizedAccessException or System.Text.Json.JsonException)
        {
            if (!token.IsCancellationRequested)
                status.Text=error is ArgumentException or InvalidOperationException or UnauthorizedAccessException
                    ?error.Message:"Could not read or save Lead routing settings.";
        }
        finally
        {
            busy=false;
            if (!token.IsCancellationRequested) editor.Enabled=saveButton.Enabled=current is not null;
        }
    }

    private void ClosingHandler(object sender,FormClosingEventArgs e) => e.Cancel=busy;
    private void ClosedHandler(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
}
