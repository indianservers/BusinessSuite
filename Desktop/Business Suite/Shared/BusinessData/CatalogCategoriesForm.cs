using Npgsql;
using System.Text.Json;

namespace Business_Suite;

public sealed partial class CatalogCategoriesForm : Form
{
    private sealed record CategoryRow(string CategoryId, string? ChildId, string Name, string Parent);
    private readonly CatalogCategoriesRepository? repository;
    private readonly CancellationTokenSource lifetime = new();
    private CatalogTaxonomy? taxonomy;
    private bool dirty;
    private bool busy;

    public CatalogCategoriesForm()
    {
        InitializeComponent();
    }

    internal CatalogCategoriesForm(DesktopDatabaseSettings settings) : this() =>
        repository = new CatalogCategoriesRepository(settings);

    private CategoryRow? Selected => categoryGrid.CurrentRow?.DataBoundItem as CategoryRow;

    private async void load_Click(object? sender, EventArgs e)
    {
        if (!ConfirmDiscard())
            return;
        await RunAsync(async repo =>
        {
            taxonomy = await repo.LoadAsync(lifetime.Token);
            dirty = false;
            Bind();
            statusLabel.Text = !taxonomy.CanEdit ? "You have read-only category access."
                : taxonomy.Categories.Count == 0 ? "No categories have been added." : "";
        });
    }

    private async void save_Click(object? sender, EventArgs e)
    {
        if (taxonomy is not { } draft || !dirty)
            return;
        await RunAsync(async repo =>
        {
            taxonomy = await repo.SaveAsync(draft, lifetime.Token);
            dirty = false;
            Bind(Selected?.ChildId ?? Selected?.CategoryId);
            statusLabel.Text = "Categories saved.";
        });
    }

    private async Task RunAsync(Func<CatalogCategoriesRepository, Task> action)
    {
        if (repository is null || busy)
            return;
        busy = true;
        UpdateActions();
        try
        {
            await action(repository);
        }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or ArgumentException
            or InvalidOperationException or UnauthorizedAccessException or JsonException)
        {
            if (!lifetime.IsCancellationRequested)
                statusLabel.Text = error is ArgumentException or InvalidOperationException or UnauthorizedAccessException
                    ? error.Message : "Could not access the catalog taxonomy in PostgreSQL.";
        }
        finally
        {
            busy = false;
            if (!lifetime.IsCancellationRequested)
                UpdateActions();
        }
    }

    private void categoryGrid_CurrentRowChanged(object? sender, Telerik.WinControls.UI.CurrentRowChangedEventArgs e)
    {
        nameBox.Text = Selected?.Name ?? "";
        UpdateActions();
    }

    private void nameBox_TextChanged(object? sender, EventArgs e) => UpdateActions();

    private void newCategory_Click(object? sender, EventArgs e)
    {
        if (taxonomy is null || !TryName(out string name))
            return;
        var category = new CatalogCategory(Guid.NewGuid().ToString("N"), name, new());
        taxonomy.Categories.Add(category);
        MarkChanged(category.Id);
    }

    private void newSubcategory_Click(object? sender, EventArgs e)
    {
        if (taxonomy is null || Selected is not { } row || !TryName(out string name))
            return;
        var category = taxonomy.Categories.Single(item => item.Id == row.CategoryId);
        var child = new CatalogCategoryChild(Guid.NewGuid().ToString("N"), name);
        category.Children.Add(child);
        MarkChanged(child.Id);
    }

    private void rename_Click(object? sender, EventArgs e)
    {
        if (taxonomy is null || Selected is not { } row || !TryName(out string name))
            return;
        var companyCategories = taxonomy.Categories;
        int index = companyCategories.FindIndex(item => item.Id == row.CategoryId);
        var category = companyCategories[index];
        if (row.ChildId is null)
            companyCategories[index] = category with { Name = name };
        else
        {
            int childIndex = category.Children.FindIndex(item => item.Id == row.ChildId);
            category.Children[childIndex] = category.Children[childIndex] with { Name = name };
        }
        MarkChanged(row.ChildId ?? row.CategoryId);
    }

    private void remove_Click(object? sender, EventArgs e)
    {
        if (taxonomy is null || Selected is not { } row)
            return;
        if (row.ChildId is null)
            taxonomy.Categories.RemoveAll(category => category.Id == row.CategoryId);
        else
            taxonomy.Categories.Single(category => category.Id == row.CategoryId)
                .Children.RemoveAll(child => child.Id == row.ChildId);
        MarkChanged(null);
    }

    private bool TryName(out string name)
    {
        name = CatalogCategoriesRepository.Normalize(nameBox.Text);
        if (name.Length > 0 && name.Length <= 120 && !name.Contains(">"))
            return true;
        statusLabel.Text = "Enter a name between 1 and 120 characters without >.";
        return false;
    }

    private void MarkChanged(string? id)
    {
        dirty = true;
        statusLabel.Text = "Unsaved changes";
        Bind(id);
    }

    private void Bind(string? id = null)
    {
        if (taxonomy is null || lifetime.IsCancellationRequested)
            return;
        categoryGrid.DataSource = taxonomy.Categories.SelectMany(category =>
            new[] { new CategoryRow(category.Id, null, category.Name, "") }
            .Concat(category.Children.Select(child =>
                new CategoryRow(category.Id, child.Id, child.Name, category.Name)))).ToList();
        if (id is not null)
            categoryGrid.CurrentRow = categoryGrid.Rows.FirstOrDefault(row =>
                row.DataBoundItem is CategoryRow item && (item.ChildId ?? item.CategoryId) == id);
        nameBox.Text = Selected?.Name ?? "";
        UpdateActions();
    }

    private void UpdateActions()
    {
        bool loaded = !busy && taxonomy is not null;
        bool editable = loaded && taxonomy?.CanEdit == true;
        bool hasName = nameBox.Text.Trim().Length > 0;
        loadButton.Enabled = !busy;
        categoryGrid.Enabled = loaded;
        nameBox.Enabled = editable;
        newCategoryButton.Enabled = editable && hasName;
        newSubcategoryButton.Enabled = renameButton.Enabled = editable && hasName && Selected is not null;
        removeButton.Enabled = editable && Selected is not null;
        saveButton.Enabled = editable && dirty;
    }

    private bool ConfirmDiscard() => !dirty || MessageBox.Show(this, "Discard unsaved changes?",
        "Catalog categories", MessageBoxButtons.YesNo, MessageBoxIcon.Question) == DialogResult.Yes;

    private void CatalogCategoriesForm_FormClosing(object? sender, FormClosingEventArgs e)
    {
        e.Cancel = busy || !ConfirmDiscard();
        if (!e.Cancel)
            lifetime.Cancel();
    }
}
