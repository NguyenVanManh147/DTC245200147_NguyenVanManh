using System.Collections.Concurrent;
using System.Net.Http.Json;
using Microsoft.AspNetCore.SignalR.Client;
using Microsoft.Extensions.DependencyInjection;
using Tracking.Contracts;

namespace Customer.Client;

// Một phiên khách hàng: REST đọc dữ liệu, SignalR chỉ nhận thay đổi.
public sealed class CustomerSession : IAsyncDisposable
{
    private readonly HttpClient http;
    private readonly HubConnection connection;
    private readonly CancellationToken stop;
    private readonly ConcurrentDictionary<string, byte> watched = new(StringComparer.OrdinalIgnoreCase);
    private readonly ConcurrentDictionary<Guid, byte> seen = new();
    private readonly SemaphoreSlim subscriptions = new(1, 1);
    private TaskCompletionSource disconnected = new(TaskCreationOptions.RunContinuationsAsynchronously);
    public Task Disconnected => disconnected.Task;

    public CustomerSession(string apiUrl, CancellationToken stop)
    {
        this.stop = stop;
        http = new HttpClient { BaseAddress = new Uri(apiUrl), Timeout = TimeSpan.FromSeconds(10) };
        connection = new HubConnectionBuilder().WithUrl(apiUrl.TrimEnd('/') + "/hubs/tracking")
            .AddJsonProtocol(o => o.PayloadSerializerOptions.Converters.Add(new System.Text.Json.Serialization.JsonStringEnumConverter<ShipmentStatus>(allowIntegerValues: false)))
            .WithAutomaticReconnect([TimeSpan.Zero, TimeSpan.FromSeconds(2), TimeSpan.FromSeconds(5), TimeSpan.FromSeconds(10)])
            .Build();
        connection.On<ShipmentEvent>("ShipmentUpdated", evt => Display(evt, "SignalR"));
        connection.Reconnecting += _ => { ConsoleView.Message("Mất kết nối, đang tự nối lại..."); return Task.CompletedTask; };
        connection.Reconnected += async _ =>
        {
            try
            {
                await subscriptions.WaitAsync(stop);
                bool recovered;
                try { recovered = await Restore(); }
                finally { subscriptions.Release(); }
                ConsoleView.Message(recovered ? "Đã kết nối lại và đồng bộ lịch sử." : "Đã kết nối lại; một số mã chưa đồng bộ, chọn đăng ký theo dõi để thử lại.");
            }
            catch (Exception ex) when (!stop.IsCancellationRequested)
            { ConsoleView.Message("Chưa đồng bộ được: " + ex.Message + ". Chọn đăng ký theo dõi để thử lại."); }
            catch (OperationCanceledException) when (stop.IsCancellationRequested) { }
        };
        connection.Closed += _ =>
        {
            disconnected.TrySetResult();
            if (!stop.IsCancellationRequested) ConsoleView.Message("Đã hết lượt nối lại. Chọn đăng ký theo dõi để kết nối lại hoặc chạy lại client.");
            return Task.CompletedTask;
        };
    }

    private static string Code(string input)
    {
        var code = input.Trim().ToUpperInvariant();
        if (code.Length == 0) throw new ArgumentException("Mã bưu gửi không được rỗng.");
        return code;
    }

    public async Task Show(string input, bool history)
    {
        var code = Code(input);
        using var response = await http.GetAsync($"/shipments/{Uri.EscapeDataString(code)}" + (history ? "/history" : ""), stop);
        ConsoleView.Message($"HTTP {(int)response.StatusCode} {response.StatusCode}");
        if (!response.IsSuccessStatusCode) { ConsoleView.Message(await response.Content.ReadAsStringAsync(stop)); return; }
        if (history)
        {
            var events = await response.Content.ReadFromJsonAsync<List<ShipmentEvent>>(WireJson.Options, stop);
            ConsoleView.Message($"Lịch sử {code}:");
            foreach (var evt in events ?? []) PrintEvent(evt, "Lịch sử");
        }
        else
        {
            var shipment = (await response.Content.ReadFromJsonAsync<Shipment>(WireJson.Options, stop))!;
            ConsoleView.Message($"Mã: {shipment.TrackingCode}\nNgười gửi: {shipment.Sender}\nNgười nhận: {shipment.Recipient}\nTrạng thái: {shipment.Status}\nVị trí: {shipment.Location}\nCập nhật: {shipment.UpdatedAt.ToLocalTime():dd/MM/yyyy HH:mm:ss}");
        }
    }

    public async Task Watch(string input)
    {
        var code = Code(input);
        await subscriptions.WaitAsync(stop);
        try
        {
            if (connection.State == HubConnectionState.Reconnecting) throw new InvalidOperationException("Đang nối lại; vui lòng thử sau.");
            if (connection.State == HubConnectionState.Disconnected)
            {
                disconnected = new(TaskCreationOptions.RunContinuationsAsynchronously);
                for (var attempt = 1; ; attempt++)
                {
                    using var timeout = CancellationTokenSource.CreateLinkedTokenSource(stop);
                    timeout.CancelAfter(TimeSpan.FromSeconds(5));
                    try { await connection.StartAsync(timeout.Token); break; }
                    catch (Exception ex) when (!stop.IsCancellationRequested && attempt < 3)
                    {
                        ConsoleView.Message($"Kết nối lần {attempt}/3 thất bại: {ex.Message}. Đang thử lại...");
                        await Task.Delay(TimeSpan.FromSeconds(attempt), stop);
                    }
                    catch (Exception ex) when (!stop.IsCancellationRequested)
                    {
                        throw new InvalidOperationException("Không thể kết nối sau 3 lần thử. Kiểm tra API và chọn đăng ký theo dõi để thử lại.", ex);
                    }
                }
                await Restore();
            }
            var added = watched.TryAdd(code, 0);
            try
            {
                using var timeout = CancellationTokenSource.CreateLinkedTokenSource(stop);
                timeout.CancelAfter(TimeSpan.FromSeconds(10));
                await connection.InvokeAsync("Watch", code, timeout.Token);
                await Recover(code);
                ConsoleView.Message("Đã đăng ký theo dõi: " + code);
            }
            catch { if (added) watched.TryRemove(code, out _); throw; }
        }
        finally { subscriptions.Release(); }
    }

    public async Task Unwatch(string input)
    {
        var code = Code(input);
        await subscriptions.WaitAsync(stop);
        try
        {
            if (!watched.TryRemove(code, out _)) { ConsoleView.Message("Chưa theo dõi mã: " + code); return; }
            if (connection.State == HubConnectionState.Connected)
            {
                try
                {
                    using var timeout = CancellationTokenSource.CreateLinkedTokenSource(stop);
                    timeout.CancelAfter(TimeSpan.FromSeconds(10));
                    await connection.InvokeAsync("Unwatch", code, timeout.Token);
                }
                catch (Exception ex) when (!stop.IsCancellationRequested) { ConsoleView.Message("Đã tắt hiển thị cục bộ; chưa xác nhận rời nhóm: " + ex.Message); }
            }
            ConsoleView.Message("Đã hủy theo dõi: " + code);
        }
        finally { subscriptions.Release(); }
    }

    public void ListWatched() => ConsoleView.Message(watched.IsEmpty ? "Chưa theo dõi bưu gửi nào." : "Các mã đang theo dõi:\n" + string.Join('\n', watched.Keys.Order()));

    private async Task<bool> Restore()
    {
        var recovered = true;
        foreach (var code in watched.Keys.Order())
        {
            try
            {
                using var timeout = CancellationTokenSource.CreateLinkedTokenSource(stop);
                timeout.CancelAfter(TimeSpan.FromSeconds(10));
                await connection.InvokeAsync("Watch", code, timeout.Token);
                await Recover(code);
            }
            catch (Exception ex) when (!stop.IsCancellationRequested)
            {
                recovered = false;
                ConsoleView.Message($"Chưa khôi phục được {code}: {ex.Message}. Đăng ký lại mã này để thử lại.");
            }
        }
        return recovered;
    }

    private async Task Recover(string code)
    {
        var events = await http.GetFromJsonAsync<List<ShipmentEvent>>($"/shipments/{Uri.EscapeDataString(code)}/history", WireJson.Options, stop);
        foreach (var evt in events ?? []) Display(evt, "REST khôi phục");
    }

    private void Display(ShipmentEvent evt, string source)
    {
        if (watched.ContainsKey(evt.TrackingCode) && seen.TryAdd(evt.EventId, 0)) PrintEvent(evt, source);
    }

    private static void PrintEvent(ShipmentEvent evt, string source) => ConsoleView.Message(
        $"[{source}] {evt.TrackingCode} v{evt.Version} {evt.Status} @ {evt.Location} — {evt.OccurredAt.ToLocalTime():dd/MM/yyyy HH:mm:ss} {evt.Note}" +
        (evt.Status == ShipmentStatus.Failed ? "\nCẢNH BÁO: Bưu gửi gặp sự cố, cần liên hệ bưu cục." : ""));

    public async ValueTask DisposeAsync()
    {
        await connection.DisposeAsync();
        http.Dispose();
    }
}

// Đồng bộ các dòng thông báo với menu; không giữ lock trong lúc đợi nhập.
public static class ConsoleView
{
    private static readonly object gate = new();
    private static string? prompt;
    public static void Message(string text)
    {
        lock (gate)
        {
            if (prompt is not null) Console.WriteLine();
            Console.WriteLine(text);
            if (prompt is not null) Console.Write(prompt);
        }
    }
    public static async Task<string?> Read(string text, CancellationToken ct)
    {
        lock (gate) { prompt = text; Console.Write(text); }
        try { return await Console.In.ReadLineAsync(ct); }
        finally { lock (gate) prompt = null; }
    }
}
