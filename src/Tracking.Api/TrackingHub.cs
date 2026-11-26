using System.Text.RegularExpressions;
using Microsoft.AspNetCore.SignalR;

namespace Tracking.Api;

// Chapter 03: REST ghi dữ liệu; hub chỉ đăng ký và đẩy thông báo.
public sealed partial class TrackingHub(ShipmentStore store) : Hub
{
    [GeneratedRegex("^BG[A-F0-9]{32}$", RegexOptions.CultureInvariant)]
    private static partial Regex CodePattern();

    public Task Watch(string trackingCode)
    {
        if (!CodePattern().IsMatch(trackingCode) || store.Get(trackingCode) is null)
            throw new HubException("Không tìm thấy mã bưu gửi hợp lệ.");
        return Groups.AddToGroupAsync(Context.ConnectionId, GroupName(trackingCode));
    }

    public Task Unwatch(string trackingCode) =>
        Groups.RemoveFromGroupAsync(Context.ConnectionId, GroupName(trackingCode));

    public static string GroupName(string trackingCode) => "shipment:" + trackingCode;
}
