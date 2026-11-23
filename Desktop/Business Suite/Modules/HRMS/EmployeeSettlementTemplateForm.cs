namespace Business_Suite;

internal sealed partial class EmployeeSettlementTemplateForm : Form
{
    private readonly EmployeeAdministrationRepository? repository;
    private readonly CancellationTokenSource lifetime = new();
    private EmployeeSettlementTemplate? current;
    private bool busy;

    public EmployeeSettlementTemplateForm() => InitializeComponent();

    internal EmployeeSettlementTemplateForm(EmployeeAdministrationRepository repository) : this() =>
        this.repository = repository;

    private async void TemplateLoaded(object? sender, EventArgs e) => await RunAsync(ReadAsync);
    private void CloseClicked(object? sender, EventArgs e) => Close();
    private void BasisChanged(object? sender, Telerik.WinControls.UI.Data.PositionChangedEventArgs e) =>
        financialMonth.Enabled = !busy && current?.CanSave == true && basis.SelectedIndex == 0;
    private async void UploadLogoClicked(object? sender, EventArgs e) => await UploadAsync("logo");
    private async void UploadSignatureClicked(object? sender, EventArgs e) => await UploadAsync("signature");

    private async Task ReadAsync()
    {
        current = await repository!.ReadSettlementTemplateAsync(lifetime.Token);
        layout.SelectedIndex = current.Layout switch { "compact" => 1, "professional" => 2, _ => 0 };
        showCode.Checked = current.ShowCode;
        footer.Text = current.Footer;
        basis.SelectedIndex = current.Year.Basis == "calendar" ? 1 : 0;
        financialMonth.SelectedIndex = current.Year.FinancialYearStart is >= 1 and <= 12
            ? current.Year.FinancialYearStart - 1 : 3;
        await ReadBrandingAsync();
        status.Text = current.CanSave ? "Changes apply to future company payroll presentation. India tax forms use April–March." :
            "Organization-wide payroll processing permission is required to save.";
    }

    private async Task ReadBrandingAsync()
    {
        var presentation = await repository!.ReadSettlementPresentationAsync(lifetime.Token);
        branding.Text = presentation.Available ?
            $"Company logo  {(presentation.Logo is null ? "not configured" : "configured")}   ·   Signature image  {(presentation.Signature is null ? "not configured" : "configured")}"
            : "Company branding settings are unavailable.";
    }

    private async Task UploadAsync(string kind)
    {
        var draft = current;
        if (!uploadLogo.Enabled || draft is null || brandFile.ShowDialog(this) != DialogResult.OK)
            return;
        await RunAsync(async () =>
        {
            var revision = await repository!.UploadSettlementBrandAsync(kind,brandFile.FileName,draft.Revision,lifetime.Token);
            current = draft with { Revision = revision };
            await ReadBrandingAsync();
            status.Text = "Branding image saved.";
        });
    }

    private async void SaveClicked(object? sender, EventArgs e)
    {
        if (!save.Enabled || current is null)
            return;
        await RunAsync(async () =>
        {
            var year = new PayrollYearPolicy(basis.SelectedIndex == 1 ? "calendar" : "financial",financialMonth.SelectedIndex + 1);
            await repository!.SaveSettlementTemplateAsync(layout.Text.ToLowerInvariant(),showCode.Checked,
                footer.Text,current.Revision,lifetime.Token,year);
            await ReadAsync();
            status.Text = "Company payroll presentation settings saved.";
        });
    }

    private async void PreviewClicked(object? sender, EventArgs e)
    {
        if (!preview.Enabled || previewFile.ShowDialog(this) != DialogResult.OK)
            return;
        await RunAsync(async () =>
        {
            var saved = await repository!.ReadSettlementPresentationAsync(lifetime.Token,preview:true);
            var logo = repository.ReadSettlementBrandAsset(saved.Logo,"logo");
            var signature = repository.ReadSettlementBrandAsset(saved.Signature,"signature");
            var bytes = EmployeeSettlementPdf.RenderPreview(saved.Company,saved.Template,logo,signature);
            File.WriteAllBytes(previewFile.FileName,bytes);
            status.Text = !saved.Available ? "Preview saved. The company profile is unavailable." :
                (saved.Logo is not null && logo is null) || (saved.Signature is not null && signature is null)
                    ? "Preview saved. A configured branding image is unavailable in local storage." : "Sample settlement preview saved.";
        });
    }

    private async Task RunAsync(Func<Task> action)
    {
        if (repository is null || busy)
            return;
        busy = true;
        UpdateActions();
        try { await action(); }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (UnauthorizedAccessException ex) { status.Text = ex.Message; }
        catch (InvalidOperationException ex) { status.Text = ex.Message; }
        catch (IOException) { status.Text = "The selected file or the local payroll branding folder is unavailable."; }
        catch (Npgsql.NpgsqlException) { status.Text = "PostgreSQL could not complete the payroll template operation."; }
        finally
        {
            busy = false;
            if (!IsDisposed)
                UpdateActions();
        }
    }

    private void UpdateActions()
    {
        save.Enabled = footer.Enabled = layout.Enabled = showCode.Enabled = !busy && current?.CanSave == true;
        basis.Enabled = save.Enabled;
        financialMonth.Enabled = save.Enabled && basis.SelectedIndex == 0;
        uploadLogo.Enabled = uploadSignature.Enabled = !busy && current?.CanSave == true;
        preview.Enabled = !busy && current is not null;
        close.Enabled = !busy;
    }

    protected override void OnFormClosed(FormClosedEventArgs e)
    {
        lifetime.Cancel();
        previewFile.Dispose();
        brandFile.Dispose();
        base.OnFormClosed(e);
    }
}
