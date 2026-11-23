namespace Business_Suite;

internal sealed partial class AppointmentTimelineForm
{
    private const int CalendarAxisWidth=62, CalendarLaneWidth=184, CalendarHeaderHeight=50, CalendarSlotHeight=26;
    private AppointmentTimelineSlot? calendarSlot;
    private readonly List<(string Caption, DateTime Date, List<AppointmentTimelineSlot> Slots)> calendarLanes=[];
    private int firstSlot, slotCount;

    private void BindCalendar(List<AppointmentTimelineSlot> slots)
    {
        calendarSlot=null;
        calendarLanes.Clear();
        calendarLanes.AddRange(slots.GroupBy(slot=>(slot.Starts.Date,slot.ProviderId))
            .OrderBy(group=>group.Key.Date).ThenBy(group=>group.First().Provider,StringComparer.CurrentCultureIgnoreCase)
            .Select(group=>(group.First().Provider,group.Key.Date,group.ToList())));
        firstSlot=slots.Count==0 ? 0 : slots.Min(slot=>CalendarIndex(slot.Starts));
        slotCount=slots.Count==0 ? 0 : slots.Max(slot=>CalendarIndex(slot.Starts))-firstSlot+1;
        calendar.AutoScrollPosition=Point.Empty;
        calendar.AutoScrollMinSize=calendarLanes.Count==0 ? Size.Empty :
            new Size(CalendarAxisWidth+calendarLanes.Count*CalendarLaneWidth,CalendarHeaderHeight+slotCount*CalendarSlotHeight);
        calendar.Invalidate();
    }

    private static int CalendarIndex(DateTime local)=>local.Hour*2+local.Minute/30;

    private Rectangle CalendarCell(int lane,AppointmentTimelineSlot slot) =>
        new(CalendarAxisWidth+lane*CalendarLaneWidth+2,
            CalendarHeaderHeight+(CalendarIndex(slot.Starts)-firstSlot)*CalendarSlotHeight+1,
            CalendarLaneWidth-4,CalendarSlotHeight-2);

    private void CalendarViewChanged(object? sender,EventArgs e)
    {
        calendar.Visible=calendarView.Checked;
        grid.Visible=!calendarView.Checked;
        calendar.Invalidate();
        UpdateActions();
    }

    private void CalendarScrolled(object? sender,ScrollEventArgs e)=>calendar.Invalidate();

    private void PaintCalendar(object? sender,PaintEventArgs e)
    {
        if(calendarLanes.Count==0)
        {
            TextRenderer.DrawText(e.Graphics,"No calendar slots for this selection.",calendar.Font,new Point(12,12),SystemColors.WindowText);
            return;
        }
        Point scroll=calendar.AutoScrollPosition;
        var viewport=new Rectangle(-scroll.X,-scroll.Y,calendar.ClientSize.Width,calendar.ClientSize.Height);
        e.Graphics.TranslateTransform(scroll.X,scroll.Y);
        int width=calendar.AutoScrollMinSize.Width;
        for(int row=0;row<slotCount;row++)
        {
            int y=CalendarHeaderHeight+row*CalendarSlotHeight;
            if(y+CalendarSlotHeight<viewport.Top || y>viewport.Bottom) continue;
            e.Graphics.DrawLine(SystemPens.ControlLight,0,y,width,y);
            DrawCalendarText(e.Graphics,DateTime.Today.AddMinutes((firstSlot+row)*30).ToString("HH:mm"),
                new Rectangle(4,y,CalendarAxisWidth-8,CalendarSlotHeight),SystemColors.WindowText);
        }
        for(int lane=0;lane<calendarLanes.Count;lane++)
        {
            int x=CalendarAxisWidth+lane*CalendarLaneWidth;
            if(x+CalendarLaneWidth<viewport.Left || x>viewport.Right) continue;
            var column=calendarLanes[lane];
            e.Graphics.FillRectangle(SystemBrushes.Control,x,0,CalendarLaneWidth-1,CalendarHeaderHeight-1);
            DrawCalendarText(e.Graphics,column.Date.ToString("ddd d MMM"),new Rectangle(x+5,1,CalendarLaneWidth-10,22),SystemColors.ControlText);
            DrawCalendarText(e.Graphics,column.Caption,new Rectangle(x+5,23,CalendarLaneWidth-10,24),SystemColors.ControlText);
            foreach(var slot in column.Slots)
            {
                var rect=CalendarCell(lane,slot);
                if(!rect.IntersectsWith(viewport)) continue;
                bool selected=ReferenceEquals(calendarSlot,slot);
                var brush=selected ? SystemBrushes.Highlight : slot.Selectable ? SystemBrushes.Info : SystemBrushes.Control;
                e.Graphics.FillRectangle(brush,rect);
                string caption=slot.Bookings.Length==1 && bookings.TryGetValue(slot.Bookings[0],out var booking) ? booking.Name :
                    slot.Bookings.Length>1 ? $"{slot.Bookings.Length} appointments" : slot.Status;
                DrawCalendarText(e.Graphics,$"{slot.Starts:HH:mm}  {caption}",Rectangle.Inflate(rect,-4,0),
                    selected ? SystemColors.HighlightText : SystemColors.ControlText);
            }
        }
    }

    private void DrawCalendarText(Graphics graphics,string text,Rectangle bounds,Color color)=>
        TextRenderer.DrawText(graphics,text,calendar.Font,bounds,color,
            TextFormatFlags.SingleLine|TextFormatFlags.EndEllipsis|TextFormatFlags.VerticalCenter|TextFormatFlags.PreserveGraphicsTranslateTransform);

    private void SelectCalendarSlot(object? sender,MouseEventArgs e)
    {
        if(e.Button!=MouseButtons.Left || busy) return;
        Point scroll=calendar.AutoScrollPosition;
        var point=new Point(e.X-scroll.X,e.Y-scroll.Y);
        int index=(point.X-CalendarAxisWidth)/CalendarLaneWidth;
        if(point.X<CalendarAxisWidth || index>=calendarLanes.Count) return;
        calendarSlot=calendarLanes[index].Slots.FirstOrDefault(slot=>CalendarCell(index,slot).Contains(point));
        if(calendarSlot is not null)
            status.Text=$"{calendarSlot.Provider} · {calendarSlot.Starts:ddd d MMM, HH:mm} · {calendarSlot.Zone} · {calendarSlot.Status}";
        calendar.Invalidate();
        UpdateActions();
    }
}
