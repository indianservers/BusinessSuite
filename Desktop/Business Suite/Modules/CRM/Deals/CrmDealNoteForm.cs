using Npgsql;

namespace Business_Suite;

public sealed partial class CrmDealNoteForm : Form
{
    private readonly CrmDealRepository? repository;
    private readonly int id;
    private readonly CancellationTokenSource lifetime=new();
    private bool saving;
    private readonly int? noteId;
    private readonly string? revision;

    public CrmDealNoteForm() => InitializeComponent();
    internal CrmDealNoteForm(CrmDealRepository repository,int id) : this()
    {
        this.repository=repository;
        this.id=id;
    }

    internal CrmDealNoteForm(CrmDealRepository repository,int id,int noteId,string revision,string body) : this(repository,id)
    {
        this.noteId=noteId;
        this.revision=revision;
        Text="Edit Deal note";
        bodyBox.Text=body;
        mentionLabel.Visible=mentionBox.Visible=mentionButton.Visible=false;
    }

    private async void NoteShown(object sender,EventArgs e)
    {
        if (repository is null || noteId.HasValue)
            return;
        var cancellation=lifetime.Token;
        try
        {
            var recipients=await repository.NoteMentionOptionsAsync(id,cancellation);
            if (cancellation.IsCancellationRequested)
                return;
            mentionBox.DisplayMember=nameof(DealCaptureChoice.Name);
            mentionBox.DataSource=recipients;
            mentionBox.SelectedIndex=recipients.Count==0?-1:0;
            mentionBox.Enabled=mentionButton.Enabled=!saving && recipients.Count>0;
        }
        catch(OperationCanceledException) when (cancellation.IsCancellationRequested) { }
        catch(Exception error) when (Expected(error))
        {
            if (!cancellation.IsCancellationRequested && !saving)
                feedback.Text="Mention recipients are unavailable. You can still save a note.";
        }
    }

    private void InsertMentionClicked(object sender,EventArgs e)
    {
        if (saving || mentionBox.SelectedItem?.DataBoundItem is not DealCaptureChoice {Id:int recipient} choice)
            return;
        string label=choice.Name.Replace("[","(").Replace("]",")");
        string text=$" @[{label}](user:{recipient}) ";
        if (bodyBox.TextLength-bodyBox.SelectionLength+text.Length>bodyBox.MaxLength)
        {
            feedback.Text="The note is too long to add this mention.";
            return;
        }
        bodyBox.SelectedText=text;
        bodyBox.Focus();
    }

    private async void SaveClicked(object sender,EventArgs e)
    {
        if (repository is null || saving)
            return;
        saving=true;
        saveButton.Enabled=cancelButton.Enabled=bodyBox.Enabled=false;
        mentionBox.Enabled=mentionButton.Enabled=false;
        feedback.Text="Saving note…";
        try
        {
            if (noteId.HasValue)
                await repository.EditDealNoteAsync(id,noteId.Value,revision!,bodyBox.Text,lifetime.Token);
            else
                await repository.AddDealNoteAsync(id,bodyBox.Text,lifetime.Token);
            saving=false;
            DialogResult=DialogResult.OK;
        }
        catch(Exception error) when(Expected(error))
        {
            feedback.Text=error is ArgumentException or InvalidOperationException or UnauthorizedAccessException
                ?error.Message:"Could not save the note. Check PostgreSQL and try again.";
        }
        finally
        {
            saving=false;
            if (!IsDisposed)
            {
                saveButton.Enabled=cancelButton.Enabled=bodyBox.Enabled=true;
                mentionBox.Enabled=mentionButton.Enabled=mentionBox.Items.Count>0;
            }
        }
    }

    private void NoteIsClosing(object sender,FormClosingEventArgs e) => e.Cancel=saving;
    private void NoteIsClosed(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
    private static bool Expected(Exception error) => error is ArgumentException or InvalidOperationException or UnauthorizedAccessException
        or IOException or NpgsqlException or TimeoutException;
}
