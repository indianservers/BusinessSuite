using Npgsql;

namespace Business_Suite;

public sealed partial class LeadSequenceForm : Form
{
    private readonly LeadKey? key;
    private LeadSequenceOptions? options;
    private bool busy;
    private readonly CancellationTokenSource lifetime=new();

    public LeadSequenceForm() => InitializeComponent();
    internal LeadSequenceForm(LeadKey key) : this() => this.key=key;

    private LeadSequenceTemplate? Selected => sequenceBox.SelectedItem?.DataBoundItem as LeadSequenceTemplate;

    private async void FormShown(object sender,EventArgs e)
    {
        if (key is null)
            return;
        await RunAsync(async cancellation =>
        {
            options=await LeadStore.SequenceOptionsAsync(key,cancellation);
            if (!cancellation.IsCancellationRequested)
            {
                currentLabel.Text=options.Current;
                sequenceBox.DisplayMember=nameof(LeadSequenceTemplate.Name);
                sequenceBox.DataSource=options.Templates;
                sequenceBox.SelectedIndex=options.Templates.Count==0?-1:0;
                feedback.Text=options.Templates.Count==0?"No sequence templates configured.":"";
            }
        });
    }

    private async void StartClicked(object sender,EventArgs e)
    {
        if (Selected is LeadSequenceTemplate chosen)
            await SaveAsync(chosen.Name);
    }

    private async void StopClicked(object sender,EventArgs e) => await SaveAsync(null);

    private async Task SaveAsync(string? template)
    {
        if (key is null)
            return;
        await RunAsync(async cancellation =>
        {
            await LeadStore.ChangeLeadSequenceAsync(key,template,cancellation);
            if (!cancellation.IsCancellationRequested)
                DialogResult=DialogResult.OK;
        });
    }

    private async Task RunAsync(Func<CancellationToken,Task> operation)
    {
        if (busy)
            return;
        var cancellation=lifetime.Token;
        busy=true;
        SelectionChanged(this,EventArgs.Empty);
        try { await operation(cancellation); }
        catch(OperationCanceledException) when(cancellation.IsCancellationRequested) { }
        catch(Exception error) when(error is NpgsqlException or IOException or InvalidOperationException or
            UnauthorizedAccessException or ArgumentException or TimeoutException)
        {
            if (!cancellation.IsCancellationRequested)
                feedback.Text=error is UnauthorizedAccessException or ArgumentException or InvalidOperationException
                    ?error.Message:"Could not access the Lead sequence in PostgreSQL.";
        }
        finally
        {
            busy=false;
            if (!cancellation.IsCancellationRequested)
                SelectionChanged(this,EventArgs.Empty);
        }
    }

    private void SelectionChanged(object sender,EventArgs e)
    {
        stepsGrid.DataSource=Selected?.Steps;
        sequenceBox.Enabled=!busy&&options?.Templates.Count>0;
        stopButton.Enabled=!busy&&options?.Active==true;
        startButton.Text=options?.Active==true?"Replace sequence":"Start sequence";
        startButton.Enabled=!busy&&options?.CanStart==true&&Selected is not null;
    }

    private void FormIsClosed(object sender,FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
}
