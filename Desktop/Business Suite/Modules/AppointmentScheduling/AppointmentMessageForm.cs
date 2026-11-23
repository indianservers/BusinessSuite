using System.ComponentModel;
using System.Diagnostics;
using System.Runtime.InteropServices;

namespace Business_Suite;

public sealed partial class AppointmentMessageForm : Form
{
    private sealed record Draft(string Recipient, string Message, bool Edited, int ReviewedRevision);

    private readonly AppointmentRepository? repository;
    private readonly int id;
    private readonly CancellationTokenSource lifetime = new();
    private readonly Draft?[] drafts = new Draft?[2];
    private AppointmentConfirmation? latest;
    private int channel;
    private bool busy;
    private bool binding;
    private bool fresh;

    public AppointmentMessageForm() => InitializeComponent();

    internal AppointmentMessageForm(AppointmentRepository repository, int id) : this()
    {
        this.repository = repository;
        this.id = id;
    }

    private async void RefreshClicked(object? sender, EventArgs e) => await RefreshAsync();

    private async Task RefreshAsync(Action? action = null)
    {
        if (repository is null || busy)
            return;
        var cancellation = lifetime.Token;
        busy = true;
        UpdateState();
        feedback.Text = "Checking latest booking details…";
        try
        {
            var summary = await repository.ConfirmationAsync(id, cancellation);
            if (cancellation.IsCancellationRequested)
                return;
            if (latest is null || summary.CustomerId != latest.CustomerId)
            {
                bool firstRead = latest is null;
                var recipient = summary.CustomerId is int customer
                    ? await repository.ConfirmationRecipientAsync(customer, cancellation)
                    : ("", "");
                if (cancellation.IsCancellationRequested)
                    return;
                string message = AppointmentMessageDraft.Generate(summary);
                int reviewed = firstRead ? summary.Revision : latest!.Revision;
                drafts[0] = new(recipient.Item1, message, false, reviewed);
                drafts[1] = new(recipient.Item2, message, false, reviewed);
                channel = recipient.Item1.Length > 0 ? 0 : 1;
            }
            else
            {
                for (int index = 0; index < drafts.Length; index++)
                    if (drafts[index] is { Edited: false } draft)
                        drafts[index] = draft with { Message = AppointmentMessageDraft.Generate(summary) };
            }
            latest = summary;
            latestText.Text = AppointmentMessageDraft.Generate(summary);
            fresh = true;
            BindDraft();
            feedback.Text = "Review the draft in your messaging app before sending. Delivery is not tracked here.";
            if (Current?.ReviewedRevision == summary.Revision)
                action?.Invoke();
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested) { }
        catch (Exception error) when (AppointmentsForm.IsExpected(error))
        {
            if (!cancellation.IsCancellationRequested)
            {
                fresh = false;
                feedback.Text = AppointmentsForm.Friendly(error);
            }
        }
        finally
        {
            if (!cancellation.IsCancellationRequested)
            {
                busy = false;
                UpdateState();
            }
        }
    }

    private Draft? Current => drafts[channel];
    private bool IsSms => channel == 1;

    private void BindDraft()
    {
        binding = true;
        channelBox.SelectedIndex = channel;
        recipientBox.Text = Current?.Recipient ?? "";
        messageBox.Text = Current?.Message ?? "";
        binding = false;
        UpdateState();
    }

    private void ChannelChanged(object? sender, EventArgs e)
    {
        if (binding || channelBox.SelectedIndex < 0)
            return;
        channel = channelBox.SelectedIndex;
        BindDraft();
    }

    private void DraftChanged(object? sender, EventArgs e)
    {
        if (binding || Current is not { } current)
            return;
        drafts[channel] = current with
        {
            Recipient = recipientBox.Text,
            Message = messageBox.Text,
            Edited = current.Edited || ReferenceEquals(sender, messageBox)
        };
        UpdateState();
    }

    private void ResetClicked(object? sender, EventArgs e)
    {
        if (latest is null || Current is not { } current || busy)
            return;
        drafts[channel] = current with
        {
            Message = AppointmentMessageDraft.Generate(latest), Edited = false, ReviewedRevision = latest.Revision
        };
        BindDraft();
    }

    private void ReviewedClicked(object? sender, EventArgs e)
    {
        if (latest is null || Current is not { } current || busy)
            return;
        drafts[channel] = current with { ReviewedRevision = latest.Revision };
        UpdateState();
    }

    private async void CopyClicked(object? sender, EventArgs e) => await RefreshAsync(() =>
    {
        if (Current is not { } draft || string.IsNullOrWhiteSpace(draft.Message))
            return;
        try
        {
            Clipboard.SetText(draft.Message);
            feedback.Text = "Copied confirmation text.";
        }
        catch (ExternalException)
        {
            feedback.Text = "Clipboard unavailable. Select and copy the visible message.";
        }
    });

    private async void OpenClicked(object? sender, EventArgs e) => await RefreshAsync(() =>
    {
        if (DraftLink() is not { } link)
            return;
        try
        {
            using var application = Process.Start(new ProcessStartInfo(link) { UseShellExecute = true });
            feedback.Text = "Draft handed to the Windows messaging app. Review it there before sending.";
        }
        catch (Exception error) when (error is Win32Exception or InvalidOperationException)
        {
            feedback.Text = "Windows could not open a messaging app for this channel. Use Copy message text.";
        }
    });

    private string? DraftLink() => latest is not null && Current is { } draft
        ? AppointmentMessageDraft.Link(IsSms, draft.Recipient, latest.Reference, draft.Message) : null;

    private void UpdateState()
    {
        bool editable = !busy && Current is not null;
        bool changed = latest is not null && Current?.ReviewedRevision != latest.Revision;
        bool ready = editable && fresh && !changed;
        string? link = DraftLink();
        channelBox.Enabled = recipientBox.Enabled = messageBox.Enabled = editable;
        refreshButton.Enabled = !busy;
        resetButton.Enabled = editable && fresh;
        reviewButton.Enabled = editable && fresh && changed;
        openButton.Text = IsSms ? "Open SMS draft" : "Open email draft";
        openButton.Enabled = ready && link is not null;
        copyButton.Enabled = ready && !string.IsNullOrWhiteSpace(Current?.Message);
        string text = Current?.Message ?? "";
        counter.Text = $"{text.Length}/8000 characters" + (IsSms ? " · " + AppointmentMessageDraft.SmsEstimate(text) : "");
        guidance.Text = changed ? "The booking changed. Reset the draft or review it against the latest booking details."
            : link?.Length > 1800 ? "This draft link is long. Use Copy message text if your app truncates it."
            : IsSms ? "Use + followed by the country code and phone number." : "Enter the customer's email address.";
    }

    private void WindowClosed(object? sender, FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
}
