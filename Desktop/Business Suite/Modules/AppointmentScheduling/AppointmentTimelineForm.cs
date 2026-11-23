using Telerik.WinControls.UI;

namespace Business_Suite;

internal sealed partial class AppointmentTimelineForm : Form
{
    private readonly AppointmentRepository? repository;
    private readonly CancellationTokenSource lifetime=new();
    private bool busy;
    private bool canBook;
    private Dictionary<int,AppointmentOption> bookings=[];
    private AppointmentTimelineSlot? lastBookingSlot;
    internal AppointmentRebookSeed? NewBooking {get;private set;}
    internal int? ExistingBooking {get;private set;}

    public AppointmentTimelineForm()=>InitializeComponent();

    internal AppointmentTimelineForm(AppointmentRepository repository,DateTime first,bool sevenDays):this()
    {
        this.repository=repository;
        date.Value=first.Date;
        week.Checked=sevenDays;
    }

    private AppointmentTimelineSlot? Selected=>calendarView.Checked ? calendarSlot : grid.CurrentRow?.DataBoundItem as AppointmentTimelineSlot;
    private async void TimelineLoaded(object? sender,EventArgs e)=>await ReadAsync();
    private async void RefreshClicked(object? sender,EventArgs e)=>await ReadAsync();
    private void CloseClicked(object? sender,EventArgs e)=>Close();
    private void OpenBookingClicked(object? sender,EventArgs e)
    {
        int id=SelectedOptionId(bookingChoice);
        if (!openBooking.Enabled || id<=0) return;
        ExistingBooking=id;
        DialogResult=DialogResult.OK;
        Close();
    }
    private void SelectionChanged(object sender,CurrentRowChangedEventArgs e)=>UpdateActions();
    private void LaneChanged(object? sender,Telerik.WinControls.UI.Data.PositionChangedEventArgs e)
    {
        if (busy) return;
        provider.DataSource=null;
        provider.Items.Clear();
        CriteriaChanged(sender,e);
    }

    private void CriteriaChanged(object? sender,EventArgs e)
    {
        if (busy) return;
        grid.DataSource=null;
        BindCalendar([]);
        status.Text="Refresh to view the new period or resource.";
        UpdateActions();
    }

    private void NewBookingClicked(object? sender,EventArgs e)
    {
        if (!newBooking.Enabled || Selected is not { Selectable:true } slot)
            return;
        NewBooking=slot.Physical
            ? new AppointmentRebookSeed(null,null,new AppointmentSlot(slot.Starts,30,0,[slot.ProviderId]),slot.StartUtc)
            : new AppointmentRebookSeed(null,null,new AppointmentSlot(slot.Starts,30,slot.ProviderId,[]));
        DialogResult=DialogResult.OK;
        Close();
    }

    private async Task ReadAsync()
    {
        if (repository is null || busy)
            return;
        busy=true;
        grid.DataSource=null;
        BindCalendar([]);
        UpdateActions();
        int selectedProvider=SelectedOptionId(provider);
        try
        {
            bool physical=lane.SelectedIndex==1;
            status.Text=physical ? "Loading resource times…" : "Loading provider times…";
            var page=await repository.ReadTimelineAsync(date.Value.Date,week.Checked,selectedProvider,physical,lifetime.Token);
            if (lifetime.IsCancellationRequested) return;
            canBook=page.CanBook;
            bookings=page.Bookings;
            var choices=new List<AppointmentOption>{new(0,physical ? "All physical resources" : "All providers")};
            choices.AddRange(page.Providers);
            provider.DisplayMember=nameof(AppointmentOption.Name);
            provider.ValueMember=nameof(AppointmentOption.Id);
            provider.DataSource=choices;
            provider.SelectedIndex=Math.Max(0,choices.FindIndex(choice=>choice.Id==selectedProvider));
            grid.DataSource=page.Slots;
            BindCalendar(page.Slots);
            status.Text=page.Slots.Count==0 ? "No future opening slots in the selected period." :
                "Select a local time to start a draft. Choose a service, then check the full booking.";
        }
        catch (OperationCanceledException) when(lifetime.IsCancellationRequested) { }
        catch (Exception error) when(AppointmentsForm.IsExpected(error))
        {
            if(!lifetime.IsCancellationRequested) status.Text=AppointmentsForm.Friendly(error);
        }
        finally
        {
            busy=false;
            if(!IsDisposed) UpdateActions();
        }
    }

    private static int SelectedOptionId(RadDropDownList list) => list.SelectedValue switch
    {
        int id=>id,
        AppointmentOption option=>option.Id,
        _=>list.SelectedItem?.DataBoundItem is AppointmentOption item ? item.Id : 0
    };

    private void UpdateActions()
    {
        date.Enabled=week.Enabled=lane.Enabled=provider.Enabled=refresh.Enabled=!busy;
        calendarView.Enabled=!busy;
        var selection=busy ? null : Selected;
        newBooking.Enabled=canBook && selection is {Selectable:true};
        if (!ReferenceEquals(lastBookingSlot,selection))
        {
            lastBookingSlot=selection;
            var choices=selection?.Bookings.Where(bookings.ContainsKey).Select(id=>bookings[id]).ToList();
            bookingChoice.DataSource=choices;
            if(choices is { Count:>0 }) bookingChoice.SelectedIndex=0;
        }
        bookingChoice.Enabled=openBooking.Enabled=!busy && bookingChoice.Items.Count>0;
    }

    protected override void OnFormClosed(FormClosedEventArgs e)
    {
        lifetime.Cancel();
        base.OnFormClosed(e);
    }
}
