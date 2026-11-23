using System.Data;
using System.Text.Json;
using Npgsql;

namespace Business_Suite;

public sealed partial class CatalogOfferingForm : Form
{
    private readonly SharedCatalogRepository? repository;
    private readonly CancellationTokenSource lifetime = new();
    private readonly int? id;
    private readonly string? revision;
    private readonly string? categoryJson;
    private readonly string? legacyCategory;
    private readonly string originalPrices = "[]";
    private CatalogPriceOption[]? editedPrices;
    private bool saving;
    private bool categoriesReady;
    private bool categoriesChanged;
    private bool synchronizingCategories;
    private string[] initialCategories = Array.Empty<string>();

    private sealed record CategoryChoice(string Id, string Label, string? ParentId = null)
    {
        public override string ToString() => Label;
    }

    public CatalogOfferingForm() => InitializeComponent();

    internal CatalogOfferingForm(SharedCatalogRepository repository, DataRow? current) : this()
    {
        this.repository = repository;
        var draft = current is null ? CatalogOfferingDraft.Empty : CatalogOfferingDraft.FromRow(current);
        if (current is not null)
        {
            id = (int)current["id"];
            revision = (string)current["revision"];
            categoryJson = current.Field<string>("category_ids");
            legacyCategory = current.Field<string>("category_name");
            originalPrices = (string)current["pricing_options"];
        }
        Text = current is null ? "New product or service" : $"Edit {draft.Kind.ToLowerInvariant()}";
        kindBox.SelectedIndex = draft.Kind == "Service" ? 1 : 0;
        kindBox.Enabled = current is null;
        nameBox.Text = draft.Name;
        codeBox.Text = draft.Code;
        unitBox.Text = draft.Unit.Length == 0 ? "unit" : draft.Unit;
        currencyBox.Text = draft.Currency;
        barcodeBox.Text = draft.Barcode;
        hsnBox.Text = draft.Hsn;
        descriptionBox.Text = draft.Description;
        priceBox.Value = draft.Price;
        taxBox.Value = draft.Tax;
        costBox.Value = draft.Cost;
        mrpBox.Value = draft.Mrp;
        reorderBox.Value = draft.Reorder;
        inventoryBox.Checked = draft.TrackInventory;
    }

    private void PricesClicked(object? sender, EventArgs e)
    {
        if (saving)
            return;
        try
        {
            var options = editedPrices ?? JsonSerializer.Deserialize<CatalogPriceOption[]>(originalPrices)
                ?? Array.Empty<CatalogPriceOption>();
            SharedCatalogRepository.ValidateAdditionalPrices(options);
            using var dialog = new CatalogPricingForm(options, currencyBox.Text, priceBox.Value);
            if (dialog.ShowDialog(this) == DialogResult.OK && dialog.Changed)
            {
                editedPrices = dialog.Prices;
                pricesButton.Text = $"Additional prices ({editedPrices.Length})";
            }
        }
        catch (Exception error) when (error is JsonException or ArgumentException)
        {
            statusLabel.Text = "Saved additional prices could not be read.";
        }
    }

    private async void OfferingLoaded(object? sender, EventArgs e)
    {
        if (repository is null)
            return;
        var cancellation = lifetime.Token;
        saveButton.Enabled = false;
        statusLabel.Text = "Loading categories…";
        try
        {
            var taxonomy = await repository.OfferingCategoriesAsync(cancellation);
            if (cancellation.IsCancellationRequested)
                return;
            var selected = categoryJson is null ? null : JsonSerializer.Deserialize<string[]>(categoryJson);
            foreach (var category in taxonomy.Categories)
            {
                categoriesBox.Items.Add(new CategoryChoice(category.Id, category.Name),
                    selected?.Contains(category.Id) ?? category.Name == legacyCategory);
                foreach (var child in category.Children)
                    categoriesBox.Items.Add(new CategoryChoice(child.Id, $"{category.Name} > {child.Name}", category.Id),
                        selected?.Contains(child.Id) == true);
            }
            initialCategories = selected ?? categoriesBox.CheckedItems.Cast<CategoryChoice>().Select(value => value.Id).ToArray();
            categoriesReady = categoriesBox.Enabled = true;
            statusLabel.Text = "";
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested) { }
        catch (Exception error) when (error is JsonException or InvalidOperationException or UnauthorizedAccessException
            or NpgsqlException or TimeoutException)
        {
            if (!cancellation.IsCancellationRequested)
                statusLabel.Text = "Categories could not be loaded. Existing assignments are preserved.";
        }
        finally
        {
            if (!cancellation.IsCancellationRequested)
                saveButton.Enabled = true;
        }
    }

    private void CategoryChecked(object? sender, ItemCheckEventArgs e)
    {
        if (!categoriesReady || synchronizingCategories || e.NewValue == e.CurrentValue)
            return;
        categoriesChanged = true;
        var changed = (CategoryChoice)categoriesBox.Items[e.Index];
        synchronizingCategories = true;
        try
        {
            for (int index = 0; index < categoriesBox.Items.Count; index++)
            {
                var item = (CategoryChoice)categoriesBox.Items[index];
                if (e.NewValue == CheckState.Checked && item.Id == changed.ParentId)
                    categoriesBox.SetItemChecked(index, true);
                if (e.NewValue == CheckState.Unchecked && item.ParentId == changed.Id)
                    categoriesBox.SetItemChecked(index, false);
            }
        }
        finally
        {
            synchronizingCategories = false;
        }
    }

    private void KindChanged(object? sender, EventArgs e)
    {
        if (inventoryBox is not null)
            inventoryBox.Enabled = kindBox.SelectedIndex == 0;
    }

    private async void SaveClicked(object? sender, EventArgs e)
    {
        if (repository is null || saving || !saveButton.Enabled)
            return;
        saving = true;
        saveButton.Enabled = cancelButton.Enabled = false;
        statusLabel.Text = "Saving offering…";
        var checkedIds = categoriesBox.CheckedItems.Cast<CategoryChoice>().Select(value => value.Id).ToArray();
        var assigned = initialCategories.Where(checkedIds.Contains).Concat(checkedIds).Distinct().ToArray();
        var draft = new CatalogOfferingDraft(kindBox.SelectedIndex == 1 ? "Service" : "Product",
            nameBox.Text, codeBox.Text, descriptionBox.Text, unitBox.Text, currencyBox.Text, barcodeBox.Text, hsnBox.Text,
            priceBox.Value, taxBox.Value, costBox.Value, mrpBox.Value, reorderBox.Value, inventoryBox.Checked,
            categoriesChanged ? assigned : null, editedPrices);
        try
        {
            await repository.SaveOfferingAsync(id, revision, draft, lifetime.Token);
            if (!IsDisposed)
            {
                DialogResult = DialogResult.OK;
                Close();
            }
        }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (error is ArgumentException or InvalidOperationException or UnauthorizedAccessException
            or NpgsqlException or TimeoutException)
        {
            if (!IsDisposed)
                statusLabel.Text = error is ArgumentException or InvalidOperationException or UnauthorizedAccessException
                    ? error.Message : "Could not save the offering in PostgreSQL.";
        }
        finally
        {
            saving = false;
            if (!IsDisposed)
                saveButton.Enabled = cancelButton.Enabled = true;
        }
    }

    protected override void OnFormClosed(FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
        base.OnFormClosed(e);
    }
}
