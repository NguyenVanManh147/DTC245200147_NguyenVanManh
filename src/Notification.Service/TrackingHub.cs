using System.Text.RegularExpressions;
using Microsoft.AspNetCore.SignalR;

namespace Notification.Service;

public sealed partial class TrackingHub : Hub
{
    [GeneratedRegex("^BG[A-F0-9]{32}$", RegexOptions.CultureInvariant)]
    private static partial Regex TrackingCodePattern();
    public Task Watch(string trackingCode)
    {
        if (!TrackingCodePattern().IsMatch(trackingCode)) throw new HubException("Mã bưu gửi không hợp lệ.");
        return Groups.AddToGroupAsync(Context.ConnectionId, "shipment:" + trackingCode);
    }
    public Task Unwatch(string trackingCode) => Groups.RemoveFromGroupAsync(Context.ConnectionId, "shipment:" + trackingCode);
}
