using System.Collections.Concurrent;
using System.Diagnostics;
using System.Net;
using System.Net.Http.Json;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using Microsoft.AspNetCore.SignalR;
using Microsoft.AspNetCore.SignalR.Client;
using Microsoft.AspNetCore.Http.Connections;
using Microsoft.Extensions.DependencyInjection;
using Tracking.Contracts;

Console.OutputEncoding = Encoding.UTF8;
var root = Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "../../../../../"));
var configuration = new DirectoryInfo(AppContext.BaseDirectory).Parent!.Name;
var apiDll = Path.Combine(root, "src/Tracking.Api/bin", configuration, "net10.0/Tracking.Api.dll");
var artifacts = Path.Combine(root, "artifacts/checks-" + Guid.NewGuid().ToString("N"));
Directory.CreateDirectory(artifacts);
using var socket = new TcpListener(IPAddress.Loopback, 0);
socket.Start();
var port = ((IPEndPoint)socket.LocalEndpoint).Port;
socket.Stop();
var address = $"http://127.0.0.1:{port}";
using var http = new HttpClient { BaseAddress = new Uri(address), Timeout = TimeSpan.FromSeconds(10) };
Process? server = null;
var log = new ConcurrentQueue<string>();
var checks = 0;
void Check(bool condition, string label)
{
    if (!condition) throw new InvalidOperationException(label);
    Console.WriteLine($"PASS {++checks:00}: {label}");
}
async Task StartServer()
{
    var start = new ProcessStartInfo("dotnet")
    {
        WorkingDirectory = Path.Combine(root, "src/Tracking.Api"), UseShellExecute = false, CreateNoWindow = true,
        RedirectStandardOutput = true, RedirectStandardError = true
    };
    start.ArgumentList.Add(apiDll);
    start.ArgumentList.Add("--urls");
    start.ArgumentList.Add(address);
    start.Environment["Storage__Path"] = Path.Combine(artifacts, "test.db");
    start.Environment["ASPNETCORE_ENVIRONMENT"] = "Production";
    server = Process.Start(start) ?? throw new InvalidOperationException("Không chạy được API.");
    server.OutputDataReceived += (_, e) => { if (e.Data is not null) log.Enqueue(e.Data); };
    server.ErrorDataReceived += (_, e) => { if (e.Data is not null) log.Enqueue(e.Data); };
    server.BeginOutputReadLine();
    server.BeginErrorReadLine();
    for (var i = 0; i < 100; i++)
    {
        if (server.HasExited) throw new InvalidOperationException("API dừng: " + string.Join('\n', log));
        try { using var ready = await http.GetAsync("/health/ready"); if (ready.IsSuccessStatusCode) return; }
        catch (HttpRequestException) { }
        await Task.Delay(100);
    }
    throw new TimeoutException("API không sẵn sàng: " + string.Join('\n', log));
}
async Task StopServer()
{
    if (server is null) return;
    if (!server.HasExited) { server.Kill(entireProcessTree: true); await server.WaitForExitAsync(); }
    server.Dispose();
    server = null;
}
async Task<HttpResponseMessage> Post(string path, object body, string? key = null)
{
    using var request = new HttpRequestMessage(HttpMethod.Post, path) { Content = JsonContent.Create(body, options: WireJson.Options) };
    if (key is not null) request.Headers.Add("Idempotency-Key", key);
    return await http.SendAsync(request);
}
async Task<Shipment> Create(string sender, string key)
{
    using var response = await Post("/shipments", new CreateShipment(sender, "Người nhận", "Thái Nguyên"), key);
    Check(response.StatusCode == HttpStatusCode.Created, "Tạo bưu gửi trả 201");
    var result = (await response.Content.ReadFromJsonAsync<Shipment>(WireJson.Options))!;
    Check(response.Headers.Location?.ToString() == "/shipments/" + result.TrackingCode, "201 có Location đúng");
    return result;
}
HubConnection Connect(ConcurrentQueue<ShipmentEvent> received)
{
    var connection = new HubConnectionBuilder().WithUrl(address + "/hubs/tracking", o => o.Transports = HttpTransportType.WebSockets)
        .AddJsonProtocol(o => o.PayloadSerializerOptions.Converters.Add(new System.Text.Json.Serialization.JsonStringEnumConverter<ShipmentStatus>(allowIntegerValues: false)))
        .Build();
    connection.On<ShipmentEvent>("ShipmentUpdated", evt => received.Enqueue(evt));
    return connection;
}
async Task WaitFor(Func<bool> predicate)
{
    using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(5));
    while (!predicate()) await Task.Delay(20, timeout.Token);
}
try
{
    await StartServer();
    using (var home = await http.GetAsync("/")) Check(home.IsSuccessStatusCode, "Chapter 01: client HTTP gọi API độc lập");
    var a = await Create("Nguyễn Văn Mạnh", "create-a");
    var b = await Create("Người gửi B", "create-b");
    Check(a.TrackingCode != b.TrackingCode && a.TrackingCode.Length == 34, "Sinh mã theo dõi riêng");
    Check(a.Status == ShipmentStatus.Created && a.Version == 1, "Trạng thái khởi tạo Created v1");
    using (var replay = await Post("/shipments", new CreateShipment("Nguyễn Văn Mạnh", "Người nhận", "Thái Nguyên"), "create-a"))
        Check((await replay.Content.ReadFromJsonAsync<Shipment>(WireJson.Options))?.TrackingCode == a.TrackingCode, "Gửi lại cùng khóa không tạo trùng");
    using (var conflict = await Post("/shipments", new CreateShipment("Khác", "Người nhận", "Thái Nguyên"), "create-a"))
        Check(conflict.StatusCode == HttpStatusCode.Conflict, "Khóa dùng với nội dung khác trả 409");
    using (var invalid = await Post("/shipments", new CreateShipment("", "An", "")))
    {
        Check(invalid.StatusCode == HttpStatusCode.BadRequest, "Dữ liệu rỗng trả 400");
        Check(invalid.Content.Headers.ContentType?.MediaType == "application/problem+json", "Lỗi có Problem Details");
    }
    using (var unknown = await http.GetAsync("/shipments/UNKNOWN")) Check(unknown.StatusCode == HttpStatusCode.NotFound, "Mã không tồn tại trả 404");
    using (var unknownHistory = await http.GetAsync("/shipments/UNKNOWN/history")) Check(unknownHistory.StatusCode == HttpStatusCode.NotFound, "Lịch sử mã không tồn tại trả 404");
    using (var invalid = await Post($"/shipments/{a.TrackingCode}/events", new AddShipmentEvent(ShipmentStatus.Delivered, "Hà Nội")))
        Check(invalid.StatusCode == HttpStatusCode.Conflict, "Chặn chuyển Created thẳng sang Delivered");
    using (var invalid = await Post($"/shipments/{a.TrackingCode}/events", new { status = "INVALID", location = "Hà Nội" }))
        Check(invalid.StatusCode == HttpStatusCode.BadRequest, "Trạng thái sai trả 400");
    using (var invalid = await Post($"/shipments/{a.TrackingCode}/events", new { status = 1, location = "Hà Nội" }))
        Check(invalid.StatusCode == HttpStatusCode.BadRequest, "Không chấp nhận enum dạng số");

    var receivedA = new ConcurrentQueue<ShipmentEvent>();
    var receivedB = new ConcurrentQueue<ShipmentEvent>();
    var receivedBoth = new ConcurrentQueue<ShipmentEvent>();
    await using (var clientA = Connect(receivedA))
    await using (var clientB = Connect(receivedB))
    await using (var both = Connect(receivedBoth))
    {
        using var connectTimeout = new CancellationTokenSource(TimeSpan.FromSeconds(15));
        Console.WriteLine("Đang kết nối ba SignalR client...");
        await Task.WhenAll(clientA.StartAsync(connectTimeout.Token), clientB.StartAsync(connectTimeout.Token), both.StartAsync(connectTimeout.Token));
        Console.WriteLine("Đã kết nối, đăng ký nhóm...");
        await clientA.InvokeAsync("Watch", a.TrackingCode, connectTimeout.Token);
        await clientB.InvokeAsync("Watch", b.TrackingCode, connectTimeout.Token);
        await both.InvokeAsync("Watch", a.TrackingCode, connectTimeout.Token);
        await both.InvokeAsync("Watch", b.TrackingCode, connectTimeout.Token);
        var invalidWatch = false;
        try { await clientA.InvokeAsync("Watch", "UNKNOWN", connectTimeout.Token); } catch (HubException) { invalidWatch = true; }
        Check(invalidWatch, "Hub từ chối theo dõi mã sai");
        using (var update = await Post($"/shipments/{a.TrackingCode}/events", new AddShipmentEvent(ShipmentStatus.InTransit, "Hà Nội", "Đã xuất kho"), "event-a-2"))
            Check(update.StatusCode == HttpStatusCode.Created, "Thêm sự kiện trả 201");
        await WaitFor(() => receivedA.Count == 1 && receivedBoth.Count == 1);
        Check(receivedA.TryPeek(out var evt) && evt.Status == ShipmentStatus.InTransit && evt.Location == "Hà Nội" && evt.Version == 2, "SignalR đẩy đúng trạng thái, vị trí và version");
        await Task.Delay(200);
        Check(receivedB.IsEmpty, "Khách theo dõi mã B không nhận thông báo mã A");
        using (var update = await Post($"/shipments/{b.TrackingCode}/events", new AddShipmentEvent(ShipmentStatus.AtHub, "Đà Nẵng")))
            Check(update.IsSuccessStatusCode, "Bưu gửi thứ hai cập nhật độc lập");
        await WaitFor(() => receivedB.Count == 1 && receivedBoth.Count == 2);
        Check(receivedBoth.Select(x => x.TrackingCode).Distinct().Count() == 2, "Một client theo dõi đồng thời hai mã đúng nhóm");
        foreach (var status in new[] { ShipmentStatus.AtHub, ShipmentStatus.Failed, ShipmentStatus.InTransit, ShipmentStatus.Delivered })
        {
            using var update = await Post($"/shipments/{a.TrackingCode}/events", new AddShipmentEvent(status, "Bưu cục nhận", "Kiểm tra " + status));
            Check(update.StatusCode == HttpStatusCode.Created, "Chuyển trạng thái hợp lệ: " + status);
        }
        await WaitFor(() => receivedA.Count == 5);
        Check(receivedA.Any(x => x.Status == ShipmentStatus.Failed), "Thông báo trạng thái Failed đến client");
        using (var invalid = await Post($"/shipments/{a.TrackingCode}/events", new AddShipmentEvent(ShipmentStatus.InTransit, "Hà Nội")))
            Check(invalid.StatusCode == HttpStatusCode.Conflict, "Delivered là trạng thái kết thúc");
        var history = (await http.GetFromJsonAsync<List<ShipmentEvent>>($"/shipments/{a.TrackingCode}/history", WireJson.Options))!;
        Check(history.Count == 6 && history.Select(x => x.Version).SequenceEqual(Enumerable.Range(1, 6).Select(x => (long)x)), "Lịch sử đầy đủ và theo thứ tự version");
        Check(history.All(x => x.OccurredAt.Offset == TimeSpan.Zero) && history.Select(x => x.EventId).Distinct().Count() == 6, "Sự kiện có UTC và EventId riêng");
        await clientB.InvokeAsync("Unwatch", b.TrackingCode);
        using (var update = await Post($"/shipments/{b.TrackingCode}/events", new AddShipmentEvent(ShipmentStatus.Delivered, "Người nhận")))
            Check(update.IsSuccessStatusCode, "Bưu gửi B giao thành công");
        await WaitFor(() => receivedBoth.Any(x => x.TrackingCode == b.TrackingCode && x.Status == ShipmentStatus.Delivered));
        await Task.Delay(200);
        Check(receivedB.Count == 1, "Unwatch dừng nhận thông báo của mã đã bỏ theo dõi");
    }

    var c = await Create("Đồng thời", "create-c");
    var concurrent = await Task.WhenAll(Enumerable.Range(0, 2).Select(_ => Post($"/shipments/{c.TrackingCode}/events", new AddShipmentEvent(ShipmentStatus.InTransit, "Hà Nội"))));
    try { Check(concurrent.Count(x => x.StatusCode == HttpStatusCode.Created) == 1 && concurrent.Count(x => x.StatusCode == HttpStatusCode.Conflict) == 1, "Hai cập nhật đồng thời không tạo trạng thái trùng"); }
    finally { foreach (var response in concurrent) response.Dispose(); }
    var afterReconnect = new ConcurrentQueue<ShipmentEvent>();
    await using var reconnecting = new HubConnectionBuilder().WithUrl(address + "/hubs/tracking")
        .AddJsonProtocol(o => o.PayloadSerializerOptions.Converters.Add(new System.Text.Json.Serialization.JsonStringEnumConverter<ShipmentStatus>(allowIntegerValues: false)))
        .WithAutomaticReconnect([TimeSpan.Zero, TimeSpan.FromMilliseconds(500), TimeSpan.FromSeconds(1), TimeSpan.FromSeconds(2), TimeSpan.FromSeconds(5)])
        .Build();
    var rejoined = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
    reconnecting.On<ShipmentEvent>("ShipmentUpdated", evt => afterReconnect.Enqueue(evt));
    reconnecting.Reconnected += async _ =>
    {
        try
        {
            await reconnecting.InvokeAsync("Watch", c.TrackingCode);
            var history = await http.GetFromJsonAsync<List<ShipmentEvent>>($"/shipments/{c.TrackingCode}/history", WireJson.Options);
            Check(history?.Count >= 2, "Sau reconnect đọc lại lịch sử REST");
            rejoined.TrySetResult();
        }
        catch (Exception ex) { rejoined.TrySetException(ex); }
    };
    using (var startTimeout = new CancellationTokenSource(TimeSpan.FromSeconds(10)))
    {
        await reconnecting.StartAsync(startTimeout.Token);
        await reconnecting.InvokeAsync("Watch", c.TrackingCode, startTimeout.Token);
    }
    await StopServer();
    await StartServer();
    await rejoined.Task.WaitAsync(TimeSpan.FromSeconds(15));
    Check(reconnecting.State == HubConnectionState.Connected, "SignalR tự nối lại sau restart API và đăng ký nhóm mới");
    using (var update = await Post($"/shipments/{c.TrackingCode}/events", new AddShipmentEvent(ShipmentStatus.AtHub, "Thái Nguyên")))
        Check(update.IsSuccessStatusCode, "Ghi cập nhật mới sau restart");
    await WaitFor(() => afterReconnect.Any(x => x.TrackingCode == c.TrackingCode && x.Status == ShipmentStatus.AtHub));
    Check(true, "Nhận live push sau khi reconnect và đăng ký lại nhóm");
    var saved = await http.GetFromJsonAsync<Shipment>($"/shipments/{a.TrackingCode}", WireJson.Options);
    Check(saved?.Status == ShipmentStatus.Delivered && saved.Version == 6, "SQLite giữ dữ liệu sau khi khởi động lại API");
    var restored = await http.GetFromJsonAsync<List<ShipmentEvent>>($"/shipments/{a.TrackingCode}/history", WireJson.Options);
    Check(restored?.Count == 6, "REST khôi phục đầy đủ các cập nhật khi client offline");
    await reconnecting.StopAsync();
    using (var terminal = await Post($"/shipments/{a.TrackingCode}/events", new AddShipmentEvent(ShipmentStatus.Delivered, "Vị trí khác")))
        Check(terminal.StatusCode == HttpStatusCode.Conflict, "Delivered không cho đổi vị trí sau khi kết thúc");

    string menuCode;
    await using (var staff = new ClientProcess(root, configuration, "Operator.Client", address))
    {
        await staff.Input("99", "1", "Người gửi từ menu", "Người nhận từ menu", "Thái Nguyên", "0");
        Check(await staff.Exit() == 0, "Operator menu tạo bưu gửi và thoát bình thường");
        Check(staff.Has("Lựa chọn không hợp lệ") && staff.Has("HTTP 201"), "Nhập sai lựa chọn không làm Operator thoát");
        var match = System.Text.RegularExpressions.Regex.Match(staff.Output, "\"trackingCode\":\\s*\"([^\"]+)\"");
        Check(match.Success, "Operator hiển thị mã bưu gửi vừa tạo");
        menuCode = match.Groups[1].Value;
        var created = await http.GetFromJsonAsync<Shipment>($"/shipments/{menuCode}", WireJson.Options);
        Check(created?.Sender == "Người gửi từ menu" && created.Location == "Thái Nguyên", "Menu gửi dữ liệu tiếng Việt đúng UTF-8");
    }
    await using (var staff = new ClientProcess(root, configuration, "Operator.Client", address))
    {
        await staff.Input("2", menuCode, "3", menuCode, "INVALID", "Hà Nội", "", "3", menuCode,
            "InTransit", "Hà Nội", "Đã xuất kho", "4", menuCode, "0");
        Check(await staff.Exit() == 0, "Operator menu tra cứu, cập nhật và xem lịch sử");
        Check(staff.Has("Sai lệnh hoặc trạng thái") && staff.Has("HTTP 201") && staff.Has("HTTP 200"), "Sai trạng thái vẫn có thể cập nhật lại từ menu");
    }

    await using (var customer = new ClientProcess(root, configuration, "Customer.Client", address))
    {
        await customer.Input("99", "1", "UNKNOWN", "1", menuCode, "2", menuCode, "3", menuCode, "5");
        await customer.WaitFor("Các mã đang theo dõi:");
        Check(customer.Has("Lựa chọn không hợp lệ") && customer.Has("HTTP 404"), "Customer menu xử lý lựa chọn sai và mã không tồn tại");
        Check(customer.Has("Người gửi: Người gửi từ menu") && customer.Has("Lịch sử " + menuCode), "Customer chủ động tra cứu và đọc lịch sử bằng REST");
        Check(customer.Has("Đã đăng ký theo dõi: " + menuCode), "Customer đăng ký theo dõi từ menu");
        using (var location = await Post($"/shipments/{menuCode}/events", new AddShipmentEvent(ShipmentStatus.InTransit, "Lào Cai", "Qua điểm trung chuyển"), "location-only"))
            Check(location.StatusCode == HttpStatusCode.Created, "Giữ nguyên trạng thái nhưng đổi vị trí trả 201");
        await customer.WaitFor("[SignalR] " + menuCode + " v3 InTransit @ Lào Cai");
        Check(true, "Console Customer nhận live push trong khi đang ở menu");
        using (var duplicate = await Post($"/shipments/{menuCode}/events", new AddShipmentEvent(ShipmentStatus.InTransit, "Lào Cai", "Ghi chú khác")))
            Check(duplicate.StatusCode == HttpStatusCode.Conflict, "Cùng trạng thái và vị trí không tạo lịch sử trùng");
        using (var replay = await Post($"/shipments/{menuCode}/events", new AddShipmentEvent(ShipmentStatus.InTransit, "Lào Cai", "Qua điểm trung chuyển"), "location-only"))
            Check(replay.IsSuccessStatusCode, "Gửi lại đúng Idempotency-Key nhận lại kết quả");
        await Task.Delay(250);
        Check(customer.Count("[SignalR] " + menuCode + " v3 ") == 1, "Console loại thông báo trùng theo EventId");
        var locationHistory = await http.GetFromJsonAsync<List<ShipmentEvent>>($"/shipments/{menuCode}/history", WireJson.Options);
        Check(locationHistory?.Count == 3 && locationHistory[^1].Location == "Lào Cai", "Đổi vị trí lưu đúng một sự kiện mới");

        await customer.Input("4", menuCode, "5");
        await customer.WaitFor("Chưa theo dõi bưu gửi nào.");
        Check(customer.Has("Đã hủy theo dõi: " + menuCode), "Customer hủy theo dõi và cập nhật danh sách");
        using (var update = await Post($"/shipments/{menuCode}/events", new AddShipmentEvent(ShipmentStatus.AtHub, "Yên Bái")))
            Check(update.IsSuccessStatusCode, "Cập nhật sau khi khách hủy theo dõi vẫn thành công");
        await Task.Delay(350);
        Check(!customer.Has("[SignalR] " + menuCode + " v4 "), "Console không nhận thông báo của mã đã hủy");

        await customer.Input("3", menuCode);
        await customer.WaitFor("[REST khôi phục] " + menuCode + " v4 ");
        Check(true, "Đăng ký lại khôi phục sự kiện đã bỏ lỡ qua REST");
        using (var update = await Post($"/shipments/{menuCode}/events", new AddShipmentEvent(ShipmentStatus.Failed, "Yên Bái")))
            Check(update.IsSuccessStatusCode, "Ghi nhận Failed cho khách đang theo dõi");
        await customer.WaitFor("CẢNH BÁO:");
        Check(true, "Console hiển thị cảnh báo Failed");

        await StopServer();
        await customer.WaitFor("Mất kết nối");
        await StartServer();
        await customer.WaitFor("Đã kết nối lại và đồng bộ lịch sử.");
        Check(true, "Console Customer thật reconnect và đăng ký lại nhóm sau restart");
        using (var update = await Post($"/shipments/{menuCode}/events", new AddShipmentEvent(ShipmentStatus.InTransit, "Nam Định")))
            Check(update.IsSuccessStatusCode, "Tiếp tục hành trình sau khi Console reconnect");
        await customer.WaitFor("[SignalR] " + menuCode + " v6 InTransit @ Nam Định");
        Check(customer.Count("[SignalR] " + menuCode + " v3 ") == 1, "Console nhận push mới và không lặp dữ liệu cũ sau reconnect");
        await customer.Input("0");
        Check(await customer.Exit() == 0, "Customer thoát menu và đóng SignalR sạch sẽ");
    }
    await using (var customer = new ClientProcess(root, configuration, "Customer.Client", address, menuCode))
    {
        await customer.WaitFor("Đang theo dõi; Ctrl+C để thoát.");
        Check(customer.Has("REST khôi phục"), "Giữ tương thích cách chạy Customer bằng đối số dòng lệnh");
    }
    await using (var staff = new ClientProcess(root, configuration, "Operator.Client", address, "get", menuCode))
    {
        Check(await staff.Exit() == 0 && staff.Has(menuCode), "Giữ tương thích lệnh tra cứu Operator bằng đối số dòng lệnh");
    }
    await StopServer();
    await using (var customer = new ClientProcess(root, configuration, "Customer.Client", address))
    {
        await customer.Input("3", menuCode);
        await customer.WaitFor("Kết nối lần 1/3 thất bại");
        await StartServer();
        await customer.WaitFor("Đã đăng ký theo dõi: " + menuCode);
        Check(true, "Console chạy trước API tự retry lần kết nối đầu và khôi phục thành công");
        await customer.Input("0");
        Check(await customer.Exit() == 0, "Thoát bình thường sau retry kết nối đầu");
    }
    await StopServer();
    await using (var customer = new ClientProcess(root, configuration, "Customer.Client", address))
    {
        await customer.Input("3", menuCode);
        await customer.WaitFor("Không thể kết nối sau 3 lần thử", 25);
        Check(true, "Retry lần kết nối đầu có giới hạn và thông báo hướng xử lý");
        await customer.Input("0");
        Check(await customer.Exit() == 0, "Hết lượt retry vẫn quay lại menu và thoát được");
    }
    Console.WriteLine($"\nTHÀNH CÔNG: {checks} kiểm tra. Log: {artifacts}");
}
catch (Exception ex)
{
    Console.Error.WriteLine(ex);
    Console.Error.WriteLine(string.Join('\n', log.TakeLast(30)));
    Environment.ExitCode = 1;
}
finally
{
    await StopServer();
    await File.WriteAllLinesAsync(Path.Combine(artifacts, "api.log"), log);
}
