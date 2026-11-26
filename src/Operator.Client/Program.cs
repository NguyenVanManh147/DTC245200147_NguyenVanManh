using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using Tracking.Contracts;

Console.OutputEncoding = Encoding.UTF8;
Console.InputEncoding = Encoding.UTF8;
using var stop = new CancellationTokenSource();
Console.CancelKeyPress += (_, e) => { e.Cancel = true; stop.Cancel(); };
using var http = new HttpClient { BaseAddress = new Uri(Environment.GetEnvironmentVariable("TRACKING_API_URL") ?? "http://localhost:5080"), Timeout = TimeSpan.FromSeconds(10) };
async Task<bool> Execute(string[] command)
{
    try
    {
        using var request = command switch
        {
            ["create", var sender, var recipient, var location] => new HttpRequestMessage(HttpMethod.Post, "/shipments")
            { Content = JsonContent.Create(new CreateShipment(sender, recipient, location), options: WireJson.Options) },
            ["get", var code] => new HttpRequestMessage(HttpMethod.Get, $"/shipments/{Uri.EscapeDataString(code)}"),
            ["history", var code] => new HttpRequestMessage(HttpMethod.Get, $"/shipments/{Uri.EscapeDataString(code)}/history"),
            ["update", var code, var status, var location, .. var rest] when !int.TryParse(status, out _) && Enum.TryParse<ShipmentStatus>(status, true, out var parsed) && Enum.IsDefined(parsed)
                => new HttpRequestMessage(HttpMethod.Post, $"/shipments/{Uri.EscapeDataString(code)}/events")
                { Content = JsonContent.Create(new AddShipmentEvent(parsed, location, string.Join(" ", rest)), options: WireJson.Options) },
            _ => throw new ArgumentException("Sai lệnh hoặc trạng thái. Chạy không có tham số để xem hướng dẫn.")
        };
        request.Headers.Add("X-Correlation-ID", Guid.NewGuid().ToString());
        if (request.Method == HttpMethod.Post)
            request.Headers.Add("Idempotency-Key", Environment.GetEnvironmentVariable("IDEMPOTENCY_KEY") ?? Guid.NewGuid().ToString());
        using var response = await http.SendAsync(request, stop.Token);
        Console.WriteLine($"HTTP {(int)response.StatusCode} {response.StatusCode}");
        var body = await response.Content.ReadAsStringAsync(stop.Token);
        try { using var json = JsonDocument.Parse(body); Console.WriteLine(JsonSerializer.Serialize(json, new JsonSerializerOptions { WriteIndented = true, Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping })); }
        catch (JsonException) { Console.WriteLine(body); }
        return response.IsSuccessStatusCode;
    }
    catch (Exception ex) when (ex is HttpRequestException or OperationCanceledException or ArgumentException)
    {
        Console.WriteLine(stop.IsCancellationRequested ? "Đã dừng thao tác." : $"Không thực hiện được: {ex.Message}");
        return false;
    }
}

if (args.Length > 0)
{
    if (!await Execute(args)) Environment.ExitCode = 1;
    return;
}
async Task<string> Read(string prompt)
{
    Console.Write(prompt);
    return await Console.In.ReadLineAsync(stop.Token) ?? throw new OperationCanceledException();
}
try
{
    while (!stop.IsCancellationRequested)
    {
        Console.WriteLine("\nNHÂN VIÊN BƯU GỬI\n1. Tạo bưu gửi\n2. Tra cứu bưu gửi\n3. Cập nhật trạng thái và vị trí\n4. Xem lịch sử hành trình\n0. Thoát");
        var choice = await Read("Chọn: ");
        if (choice == "0") break;
        string[] command;
        switch (choice)
        {
            case "1": command = ["create", await Read("Người gửi: "), await Read("Người nhận: "), await Read("Vị trí ban đầu: ")]; break;
            case "2": command = ["get", (await Read("Mã bưu gửi: ")).Trim().ToUpperInvariant()]; break;
            case "3":
                var code = (await Read("Mã bưu gửi: ")).Trim().ToUpperInvariant();
                Console.WriteLine("Trạng thái: Created, InTransit, AtHub, Delivered, Failed. Giữ nguyên trạng thái nếu chỉ đổi vị trí.");
                command = ["update", code, await Read("Trạng thái: "), await Read("Vị trí: "), await Read("Ghi chú (có thể bỏ trống): ")];
                break;
            case "4": command = ["history", (await Read("Mã bưu gửi: ")).Trim().ToUpperInvariant()]; break;
            default: Console.WriteLine("Lựa chọn không hợp lệ. Vui lòng chọn 0–4."); continue;
        }
        await Execute(command);
    }
}
catch (OperationCanceledException) { }
Console.WriteLine("Đã thoát ứng dụng nhân viên.");
