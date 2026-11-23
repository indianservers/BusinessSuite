using Npgsql;

namespace Business_Suite;

public sealed partial class LeadAssignmentForm : Form
{
    private sealed record OwnerChoice(int? Id,string Name);
    private readonly CancellationTokenSource lifetime=new();
    private readonly LeadKey? lead;
    private bool busy;

    public LeadAssignmentForm() => InitializeComponent();

    internal LeadAssignmentForm(LeadKey key) : this() => lead=key;

    private async void FormShown(object sender,EventArgs e)
    {
        if (lead is not LeadKey key) return;
        await RunAsync(async token =>
        {
            var result=await LeadStore.ReadLeadAssignmentAsync(key,token);
            if (token.IsCancellationRequested) return;
            var owners=new List<OwnerChoice> {new(null,"Unassigned")};
            owners.AddRange(result.People.Select(person=>new OwnerChoice(person.Id,person.Name)));
            ownerBox.DataSource=owners;
            ownerBox.SelectedIndex=owners.FindIndex(owner=>owner.Id==result.CurrentOwner);
            feedback.Text="";
        });
    }

    private async void SaveClicked(object sender,EventArgs e)
    {
        if (lead is not LeadKey key || ownerBox.SelectedItem is not OwnerChoice owner) return;
        await RunAsync(async token =>
        {
            await LeadStore.AssignLeadAsync(key,owner.Id,reasonBox.Text,token);
            if (token.IsCancellationRequested) return;
            busy=false;
            DialogResult=DialogResult.OK;
            Close();
        });
    }

    private async Task RunAsync(Func<CancellationToken,Task> action)
    {
        if (busy) return;
        busy=true;
        ownerBox.Enabled=reasonBox.Enabled=saveButton.Enabled=false;
        var token=lifetime.Token;
        try { await action(token); }
        catch (OperationCanceledException) when (token.IsCancellationRequested) { }
        catch(Exception error) when (error is NpgsqlException or TimeoutException or IOException or
            ArgumentException or InvalidOperationException or UnauthorizedAccessException)
        {
            if (!token.IsCancellationRequested)
                feedback.Text=error is ArgumentException or InvalidOperationException or UnauthorizedAccessException
                    ?error.Message:"Could not read or save Lead ownership.";
        }
        finally
        {
            busy=false;
            if (!token.IsCancellationRequested)
                ownerBox.Enabled=reasonBox.Enabled=saveButton.Enabled=ownerBox.DataSource is not null;
        }
    }

    private void ClosingHandler(object sender,FormClosingEventArgs e) => e.Cancel=busy;
    private void ClosedHandler(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
}
