using System.Data;
using Npgsql;

namespace Business_Suite;

public sealed partial class CrmDealCollaboratorsForm : Form
{
    private readonly CrmDealRepository? repository;
    private readonly int deal;
    private readonly CancellationTokenSource lifetime=new();
    private DealCollaboratorData? data;
    private bool busy;

    public CrmDealCollaboratorsForm() => InitializeComponent();

    internal CrmDealCollaboratorsForm(CrmDealRepository repository,int id) : this()
    {
        this.repository=repository;
        deal=id;
    }

    private async void FormShown(object sender,EventArgs e) => await RunAsync(LoadAsync);
    private async void RefreshClicked(object sender,EventArgs e) => await RunAsync(LoadAsync);
    private async void SaveClicked(object sender,EventArgs e)
    {
        if (personBox.SelectedItem is DealCaptureChoice {Id: int user})
            await SaveAsync(user,roleBox.Text,watchingBox.Checked);
    }
    private async void RemoveClicked(object sender,EventArgs e)
    {
        if (grid.CurrentRow?.DataBoundItem is DataRowView row)
            await SaveAsync((int)row["user_id"],null,false);
    }

    private Task SaveAsync(int user,string? role,bool watching) => RunAsync(async token =>
    {
        var row=data?.Rows.Rows.Cast<DataRow>().FirstOrDefault(item=>(int)item["user_id"]==user);
        await repository!.SaveCollaboratorAsync(deal,user,role,watching,row?["revision"] as string,token);
        await LoadAsync(token);
    });

    private async Task LoadAsync(CancellationToken token)
    {
        var next=await repository!.CollaboratorsAsync(deal,token);
        if (token.IsCancellationRequested) return;
        data=next;
        grid.DataSource=next.Rows;
        personBox.DataSource=next.Candidates;
        personBox.SelectedIndex=-1;
        roleBox.SelectedItem=next.CanAssign?"Collaborator":"Watcher";
        watchingBox.Checked=true;
        statusText.Text=next.Rows.Rows.Count==0?"No additional collaborators.":"";
    }

    private void SelectionChanged(object sender,EventArgs e) => UpdateActions();

    private void PickedPerson(object sender,EventArgs e)
    {
        if (personBox.SelectedItem is DealCaptureChoice person && data is not null)
        {
            var row=data.Rows.Rows.Cast<DataRow>().FirstOrDefault(item=>(int)item["user_id"]==person.Id);
            roleBox.SelectedItem=data.CanAssign?(row?["role"] as string ?? "Collaborator"):"Watcher";
            watchingBox.Checked=row?["watching"] is not false;
        }
        UpdateActions();
    }

    private void UpdateActions()
    {
        bool available=!busy && data is not null;
        personBox.Enabled=watchingBox.Enabled=available;
        roleBox.Enabled=available && data!.CanAssign;
        saveButton.Enabled=available && personBox.SelectedIndex>=0 && roleBox.SelectedIndex>=0;
        removeButton.Enabled=available && grid.CurrentRow?.DataBoundItem is DataRowView row &&
            (data!.CanAssign || (int)row["user_id"]==data.Actor);
        refreshButton.Enabled=!busy;
    }

    private async Task RunAsync(Func<CancellationToken,Task> action)
    {
        if (repository is null || busy) return;
        var token=lifetime.Token;
        busy=true;
        UpdateActions();
        try { await action(token); }
        catch(OperationCanceledException) when (token.IsCancellationRequested) { }
        catch(Exception error) when (error is UnauthorizedAccessException or InvalidOperationException or
            ArgumentException or NpgsqlException or TimeoutException)
        {
            if (!token.IsCancellationRequested)
                statusText.Text=error is NpgsqlException or TimeoutException?"Could not update collaborators. Check PostgreSQL.":error.Message;
        }
        finally
        {
            busy=false;
            if (!token.IsCancellationRequested) UpdateActions();
        }
    }

    private void FormClosedHandler(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
}
