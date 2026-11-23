using Npgsql;

namespace Business_Suite;

public sealed partial class CrmDealStakeholdersForm : Form
{
    private readonly CrmDealRepository? repository;
    private readonly int id;
    private readonly CancellationTokenSource lifetime=new();
    private readonly List<DealStakeholder> draft=[];
    private DealStakeholderSnapshot? snapshot;
    private bool saving;
    private bool binding;

    public CrmDealStakeholdersForm() => InitializeComponent();
    internal CrmDealStakeholdersForm(CrmDealRepository repository,int id) : this()
    {
        this.repository=repository;
        this.id=id;
    }

    private async void FormShown(object sender,EventArgs e)
    {
        if (repository is null)
            return;
        var cancellation=lifetime.Token;
        try
        {
            var loaded=await repository.StakeholdersAsync(id,cancellation);
            if (cancellation.IsCancellationRequested)
                return;
            snapshot=loaded;
            contactBox.DisplayMember=nameof(DealCaptureChoice.Name);
            contactBox.DataSource=loaded.Contacts;
            draft.AddRange(loaded.Links);
            Bind();
            feedback.Text=loaded.Contacts.Count==0?"No eligible contacts in this branch."
                :"Choose a contact and use Add / update to apply the row before saving.";
        }
        catch(OperationCanceledException) when(cancellation.IsCancellationRequested) { }
        catch(Exception error) when(Expected(error))
        {
            if (!cancellation.IsCancellationRequested)
                feedback.Text=Friendly(error);
        }
    }

    private void Bind()
    {
        if (snapshot is null)
            return;
        binding=true;
        var names=snapshot.Contacts.Where(row=>row.Id.HasValue).ToDictionary(row=>row.Id!.Value,row=>row.Name);
        grid.DataSource=draft.Select(link=>new StakeholderRow(link,names[link.ContactId])).ToList();
        binding=false;
        SetSelection();
    }

    private void SelectionChanged(object sender,EventArgs e)
    {
        if (!binding)
            SetSelection();
    }

    private void SetSelection()
    {
        if (snapshot is null)
            return;
        var link=(grid.CurrentRow?.DataBoundItem as StakeholderRow)?.Link;
        if (link is not null)
            contactBox.SelectedIndex=snapshot.Contacts.FindIndex(choice=>choice.Id==link.ContactId);
        roleBox.Text=link?.Role??"Stakeholder";
        influenceBox.Text=link?.Influence??"";
        notesBox.Text=link?.Notes??"";
        primaryBox.Checked=link?.Primary??false;
        UpdateActions();
    }

    private void ContactChanged(object sender,EventArgs e)
    {
        if (snapshot is null || binding)
            return;
        var choice=contactBox.SelectedItem?.DataBoundItem as DealCaptureChoice;
        var link=draft.FirstOrDefault(item=>item.ContactId==choice?.Id);
        roleBox.Text=link?.Role??"Stakeholder";
        influenceBox.Text=link?.Influence??"";
        notesBox.Text=link?.Notes??"";
        primaryBox.Checked=link?.Primary??false;
        UpdateActions();
    }

    private void PutLinkClicked(object sender,EventArgs e)
    {
        if (saving || (contactBox.SelectedItem?.DataBoundItem as DealCaptureChoice)?.Id is not int contact)
            return;
        int index=draft.FindIndex(link=>link.ContactId==contact);
        if (index<0 && draft.Count>=25)
        {
            feedback.Text="This editor supports up to 25 stakeholders.";
            return;
        }
        var row=new DealStakeholder(contact,roleBox.Text,influenceBox.Text,notesBox.Text,primaryBox.Checked || draft.Count==0);
        if (row.Role.Length>80)
        {
            feedback.Text="Enter a stakeholder role of up to 80 characters.";
            return;
        }
        if (row.Primary)
            for (int offset=0;offset<draft.Count;offset++)
                draft[offset]=draft[offset] with {Primary=false};
        if (index>=0) draft[index]=row;
        else draft.Add(row);
        Bind();
        feedback.Text="Select Save to apply stakeholder changes.";
    }

    private void RemoveClicked(object sender,EventArgs e)
    {
        if (saving || grid.CurrentRow?.DataBoundItem is not StakeholderRow row)
            return;
        draft.RemoveAll(link=>link.ContactId==row.Link.ContactId);
        Bind();
        feedback.Text="Select Save to apply stakeholder changes.";
    }

    private async void SaveClicked(object sender,EventArgs e)
    {
        if (repository is null || snapshot is null || saving)
            return;
        saving=true;
        UpdateActions();
        feedback.Text="Saving stakeholders…";
        try
        {
            await repository.SaveStakeholdersAsync(snapshot,draft,lifetime.Token);
            saving=false;
            DialogResult=DialogResult.OK;
        }
        catch(Exception error) when(Expected(error))
        {
            feedback.Text=Friendly(error);
        }
        finally
        {
            saving=false;
            if (!IsDisposed)
                UpdateActions();
        }
    }

    private void UpdateActions()
    {
        saveButton.Enabled=snapshot is not null && !saving;
        applyLinkButton.Enabled=saveButton.Enabled && contactBox.SelectedIndex>=0;
        removeButton.Enabled=saveButton.Enabled && grid.CurrentRow?.DataBoundItem is StakeholderRow;
        cancelButton.Enabled=!saving;
        grid.Enabled=contactBox.Enabled=roleBox.Enabled=influenceBox.Enabled=notesBox.Enabled=primaryBox.Enabled=!saving;
    }

    private void FormIsClosing(object sender,FormClosingEventArgs e) => e.Cancel=saving;
    private void FormIsClosed(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }

    private static bool Expected(Exception error) => error is NpgsqlException or TimeoutException or IOException or
        ArgumentException or InvalidOperationException or UnauthorizedAccessException;
    private static string Friendly(Exception error) => error is ArgumentException or InvalidOperationException or UnauthorizedAccessException
        ? error.Message : "Could not complete the stakeholder operation. Check PostgreSQL and try again.";

    private sealed record StakeholderRow(DealStakeholder Link,string ContactName)
    {
        public string Role=>Link.Role;
        public string Influence=>Link.Influence;
        public string Notes=>Link.Notes;
        public bool Primary=>Link.Primary;
    }
}
