using System.Data;
using System.Globalization;
using Telerik.WinControls.UI;

namespace Business_Suite;

internal sealed partial class PmsResourceAllocationsForm : Form
{
    private readonly DataTable? rows;
    private bool binding;

    public PmsResourceAllocationsForm() => InitializeComponent();

    internal PmsResourceAllocationsForm(DataTable allocations, string title) : this()
    {
        rows = allocations;
        heading.Text = title;
    }

    private void AllocationsLoaded(object? sender, EventArgs e)
    {
        if (rows is null)
            return;
        binding = true;
        BindChoices(taskFilter, "All tasks", "task_id", row => $"{row["task_key"]} · {row["title"]}");
        BindChoices(personFilter, "All assignees", "user_id", row => Convert.ToString(row["person"], CultureInfo.CurrentCulture) ?? "");
        binding = false;
        ApplyFilters();
    }

    private void BindChoices(RadDropDownList editor, string all, string idColumn, Func<DataRow, string> label)
    {
        editor.Items.Clear();
        editor.Items.Add(new RadListDataItem(all) { Value = 0 });
        var choices = rows!.Rows.Cast<DataRow>().GroupBy(row => row.Field<int>(idColumn))
            .Select(group => (Id: group.Key, Label: label(group.First()))).OrderBy(choice => choice.Label);
        foreach (var choice in choices)
            editor.Items.Add(new RadListDataItem(choice.Label) { Value = choice.Id });
        editor.SelectedIndex = 0;
    }

    private void FiltersChanged(object? sender, Telerik.WinControls.UI.Data.PositionChangedEventArgs e)
    {
        if (!binding)
            ApplyFilters();
    }

    private void ApplyFilters()
    {
        if (rows is null)
            return;
        var conditions = new List<string>();
        if (taskFilter.SelectedItem?.Value is int task && task > 0)
            conditions.Add("task_id=" + task.ToString(CultureInfo.InvariantCulture));
        if (personFilter.SelectedItem?.Value is int person && person > 0)
            conditions.Add("user_id=" + person.ToString(CultureInfo.InvariantCulture));
        var view = new DataView(rows, string.Join(" AND ", conditions), "date, task_key, person", DataViewRowState.CurrentRows);
        grid.DataSource = view;
        decimal total = view.Cast<DataRowView>().Sum(row => row.Row.Field<decimal>("hours"));
        status.Text = view.Count == 0 ? "No daily allocations match these filters."
            : $"{view.Count:N0} allocations · {total:N4} hours";
    }
}
