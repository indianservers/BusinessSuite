using Npgsql;

namespace Business_Suite;

public sealed partial class SalesRecurringScheduleForm : Form
{
    private readonly SalesOrderRepository? repository;
    private readonly int order;
    private readonly int engagement;
    private readonly SalesBillingPlanRow? plan;
    private readonly Guid request = Guid.NewGuid();
    private bool saving;
    private bool loadingReferences;

    public SalesRecurringScheduleForm() => InitializeComponent();
    internal SalesRecurringScheduleForm(SalesOrderRepository repository, int order, int engagement, SalesBillingPlanRow plan) : this()
    {
        this.repository = repository;
        this.order = order;
        this.engagement = engagement;
        this.plan = plan;
        headingLabel.Text = $"Recurring schedule · {plan.Currency}";
        string[] rules = { "daily", "weekly", "monthly", "quarterly", "yearly" };
        ruleBox.DataSource = rules;
        string rule = plan.Rule.Trim().ToLowerInvariant();
        if (rule == "annually")
            rule = "yearly";
        ruleBox.SelectedIndex = rule.Length == 0 ? 2 : Array.IndexOf(rules, rule);
        templateBox.DataSource = new[] { "standard", "compact", "detailed" };
        templateBox.SelectedIndex = 0;
        ApplyState();
    }

    internal SalesRecurringScheduleResult? Result { get; private set; }

    private async void FormShown(object sender, EventArgs e)
    {
        if (repository is null || plan is null)
            return;
        loadingReferences = true;
        ApplyState();
        try
        {
            var choices = await repository.SalesRecurringReferencesAsync(order, engagement, plan.Id);
            if (IsDisposed)
                return;
            BindReferences(paymentModeBox, choices, "payment", "Company default");
            BindReferences(salespersonBox, choices, "salesperson", "Not assigned");
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException)
        {
            if (!IsDisposed)
                statusLabel.Text = "Could not load payment or salesperson choices. Company defaults remain available.";
        }
        finally
        {
            loadingReferences = false;
            if (!IsDisposed)
                ApplyState();
        }
    }

    private static void BindReferences(Telerik.WinControls.UI.RadDropDownList picker, List<SalesRecurringReference> choices,
        string kind, string defaultText)
    {
        var rows = new List<SalesRecurringReference> { new(kind, null, defaultText) };
        rows.AddRange(choices.Where(choice => choice.Kind == kind));
        picker.DisplayMember = nameof(SalesRecurringReference.Name);
        picker.DataSource = rows;
        picker.SelectedIndex = 0;
    }

    private void EndChanged(object sender, EventArgs e) => ApplyState();
    private void OngoingChanged(object sender, EventArgs e)
    {
        if (ongoingBox.Checked)
            endBox.Checked = false;
        ApplyState();
    }
    private void GuardClosing(object sender, FormClosingEventArgs e) => e.Cancel = saving && DialogResult != DialogResult.OK;
    private async void ExtendClicked(object sender, EventArgs e)
    {
        if (repository is null || plan is null || saving)
            return;
        saving = true;
        ApplyState();
        try
        {
            Result = await repository.ExtendSalesRecurringScheduleAsync(order, engagement, plan.Id, extendPicker.Value.Date);
            DialogResult = DialogResult.OK;
        }
        catch (Exception error) when (error is ArgumentException or NpgsqlException or TimeoutException or
            InvalidOperationException or UnauthorizedAccessException)
        {
            if (!IsDisposed)
                statusLabel.Text = error is NpgsqlException or TimeoutException
                    ? "Could not confirm the extension. Reload the plan and try the same date." : error.Message;
        }
        finally
        {
            saving = false;
            if (!IsDisposed)
                ApplyState();
        }
    }

    private async void SaveClicked(object sender, EventArgs e)
    {
        if (repository is null || plan is null || saving)
            return;
        saving = true;
        ApplyState();
        try
        {
            var input = new SalesRecurringScheduleInput(request, startPicker.Value.Date,
                endBox.Checked ? endPicker.Value.Date : null, amountBox.Value, (int)countBox.Value, (int)intervalBox.Value,
                ruleBox.Text, (int)paymentTermsBox.Value, templateBox.Text, subjectBox.Text.Trim(),
                notesBox.Text, termsBox.Text, orderNumberBox.Text.Trim())
            {
                Ongoing = ongoingBox.Checked,
                AutomaticDrafts = automaticBox.Checked,
                SuppressRecurringNotice = !notifyBox.Checked,
                PaymentMode = (paymentModeBox.SelectedItem?.DataBoundItem as SalesRecurringReference)?.Id,
                Salesperson = (salespersonBox.SelectedItem?.DataBoundItem as SalesRecurringReference)?.Id
            };
            Result = await repository.CreateSalesRecurringScheduleAsync(order, engagement, plan.Id, input);
            DialogResult = DialogResult.OK;
        }
        catch (Exception error) when (error is ArgumentException or NpgsqlException or TimeoutException or
            InvalidOperationException or UnauthorizedAccessException)
        {
            if (!IsDisposed)
                statusLabel.Text = error is NpgsqlException or TimeoutException ? "Could not confirm the schedule. Retry the same settings."
                    : error.Message;
        }
        finally
        {
            saving = false;
            if (!IsDisposed)
                ApplyState();
        }
    }

    private void ApplyState()
    {
        if (saveButton is null)
            return;
        bool enabled = !saving && !loadingReferences && plan is not null;
        ruleBox.Enabled = enabled && string.IsNullOrWhiteSpace(plan?.Rule);
        amountBox.Enabled = startPicker.Enabled = ongoingBox.Enabled = countBox.Enabled = intervalBox.Enabled = enabled;
        endBox.Enabled = enabled && !ongoingBox.Checked;
        paymentTermsBox.Enabled = templateBox.Enabled = subjectBox.Enabled = notesBox.Enabled = termsBox.Enabled = orderNumberBox.Enabled = enabled;
        paymentModeBox.Enabled = enabled && paymentModeBox.Items.Count > 0;
        salespersonBox.Enabled = enabled && salespersonBox.Items.Count > 0;
        automaticBox.Enabled = notifyBox.Enabled = enabled;
        endPicker.Enabled = enabled && endBox.Checked;
        extendPicker.Enabled = extendButton.Enabled = enabled && plan is { Status: "active", Rule.Length: > 0 };
        saveButton.Enabled = enabled;
    }
}
