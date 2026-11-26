using System.Collections.Concurrent;
using System.Net.Http.Json;
using System.Text;
using Microsoft.AspNetCore.SignalR.Client;
using Microsoft.Extensions.DependencyInjection;
using Tracking.Contracts;

Console.OutputEncoding = Encoding.UTF8;
if (args.Length == 0)
{
    Console.WriteLine("Khách hàng: dotnet run --project src/Customer.Client -- <mã bưu gửi> [mã thứ hai ...]");
    return;
}
var apiUrl = Environment.GetEnvironmentVariable("TRACKING_API_URL") ?? "http://localhost:5080";
using var http = new HttpClient { BaseAddress = new Uri(apiUrl), Timeout = TimeSpan.FromSeconds(10) };
using var stop = new CancellationTokenSource();
Console.CancelKeyPress += (_, e) => { e.Cancel = true; stop.Cancel(); };
var seen = new ConcurrentDictionary<Guid, byte>();
void Display(ShipmentEvent evt, string source)
{
    if (!seen.TryAdd(evt.EventId, 0)) return;
    Console.WriteLine($"[{source}] {evt.TrackingCode} v{evt.Version} {evt.Status} @ {evt.Location} — {evt.OccurredAt.ToLocalTime():HH:mm:ss} {evt.Note}");
    if (evt.Status == ShipmentStatus.Failed) Console.WriteLine("CẢNH BÁO: Bưu gửi gặp sự cố, cần liên hệ bưu cục.");
}
await using var connection = new HubConnectionBuilder()
    .WithUrl(apiUrl.TrimEnd('/') + "/hubs/tracking")
    .AddJsonProtocol(o => o.PayloadSerializerOptions.Converters.Add(new System.Text.Json.Serialization.JsonStringEnumConverter<ShipmentStatus>(allowIntegerValues: false)))
    .WithAutomaticReconnect(new[] { TimeSpan.Zero, TimeSpan.FromSeconds(2), TimeSpan.FromSeconds(5), TimeSpan.FromSeconds(10) })
    .Build();
connection.On<ShipmentEvent>("ShipmentUpdated", evt => Display(evt, "SignalR"));
async Task SubscribeAndRecover()
{
    foreach (var code in args.Distinct())
    {
        await connection.InvokeAsync("Watch", code, stop.Token);
        try
        {
            var events = await http.GetFromJsonAsync<List<ShipmentEvent>>($"/shipments/{Uri.EscapeDataString(code)}/history", WireJson.Options, stop.Token);
            foreach (var evt in events ?? []) Display(evt, "REST khôi phục");
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException)
        { Console.Error.WriteLine($"Không đọc được lịch sử {code}: {ex.Message}. Có thể khởi động lại client để đồng bộ."); }
    }
}
connection.Reconnecting += ex => { Console.WriteLine($"Đang nối lại: {ex?.Message}"); return Task.CompletedTask; };
connection.Reconnected += async _ =>
{
    try { await SubscribeAndRecover(); }
    catch (Exception ex) { Console.Error.WriteLine($"Đăng ký lại thất bại: {ex.Message}"); }
};
var disconnected = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
connection.Closed += _ => { disconnected.TrySetResult(); return Task.CompletedTask; };
try
{
    for (var attempt = 0; !stop.IsCancellationRequested; attempt++)
    {
        try { await connection.StartAsync(stop.Token); break; }
        catch (Exception ex) when (ex is HttpRequestException or IOException)
        {
            var delay = Math.Min(15, 1 << Math.Min(attempt, 4));
            Console.Error.WriteLine($"Chưa kết nối được dịch vụ thông báo: {ex.Message}; thử lại sau {delay}s.");
            await Task.Delay(TimeSpan.FromSeconds(delay), stop.Token);
        }
    }
    await SubscribeAndRecover();
    Console.WriteLine("Đang theo dõi; Ctrl+C để thoát. Thông báo có thể đến lại, EventId giúp loại trùng.");
    await Task.WhenAny(disconnected.Task, Task.Delay(Timeout.Infinite, stop.Token));
    if (!stop.IsCancellationRequested)
    {
        Console.Error.WriteLine("Đã hết lượt nối lại. Chạy lại client khi dịch vụ sẵn sàng; lịch sử REST sẽ khôi phục thông tin.");
        Environment.ExitCode = 1;
    }
}
catch (OperationCanceledException) when (stop.IsCancellationRequested) { }
catch (Exception ex) { Console.Error.WriteLine(ex.Message); Environment.ExitCode = 1; }
