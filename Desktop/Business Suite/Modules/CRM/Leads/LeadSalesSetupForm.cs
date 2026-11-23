using Npgsql;

namespace Business_Suite;

public sealed partial class LeadSalesSetupForm : Form
{
    private readonly CancellationTokenSource lifetime=new();
    private LeadSalesSetup? current;
    private bool busy;

    public LeadSalesSetupForm() => InitializeComponent();

    private async void FormShownHandler(object sender,EventArgs e) => await RunAsync(async token =>
    {
        var setup=await LeadStore.ReadLeadSalesSetupAsync(token);
        if (token.IsCancellationRequested) return;
        current=setup;
        managerBox.DataSource=setup.Managers;
        managerBox.SelectedIndex=setup.Managers.FindIndex(person=>person.Id==setup.Manager);
        ownerList.Items.Clear();
        foreach (var owner in setup.People)
            ownerList.Items.Add(owner,setup.Owners.Contains(owner.Id));
        feedback.Text=setup.Pipeline is int pipeline?$"Configured pipeline #{pipeline}.":"Sales process setup required.";
    });

    private async void SaveClicked(object sender,EventArgs e)
    {
        if (current is null || managerBox.SelectedItem is not LeadSalesChoice manager) return;
        await RunAsync(async token =>
        {
            var chosen=ownerList.CheckedItems.Cast<LeadSalesChoice>().Select(owner=>owner.Id).ToArray();
            int[] owners=current.Owners.Where(chosen.Contains).Concat(chosen.Where(id=>!current.Owners.Contains(id))).ToArray();
            await LeadStore.SaveLeadSalesSetupAsync(current.Revision,manager.Id,owners,token);
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
        saveButton.Enabled=managerBox.Enabled=ownerList.Enabled=false;
        var token=lifetime.Token;
        try { await action(token); }
        catch (OperationCanceledException) when (token.IsCancellationRequested) { }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or IOException or
            ArgumentException or InvalidOperationException or UnauthorizedAccessException or System.Text.Json.JsonException)
        {
            if (!token.IsCancellationRequested)
                feedback.Text=error is ArgumentException or InvalidOperationException or UnauthorizedAccessException
                    ?error.Message:"Could not read or save sales process settings.";
        }
        finally
        {
            busy=false;
            if (!token.IsCancellationRequested)
                saveButton.Enabled=managerBox.Enabled=ownerList.Enabled=current is not null;
        }
    }

    private void ClosingHandler(object sender,FormClosingEventArgs e) => e.Cancel=busy;

    private void ClosedHandler(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
}
