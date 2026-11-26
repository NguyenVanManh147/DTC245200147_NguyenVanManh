using System.Net.Http.Json;
using System.Text;
using Tracking.Contracts;

Console.OutputEncoding = Encoding.UTF8;
using var http = new HttpClient { BaseAddress = new Uri(Environment.GetEnvironmentVariable("TRACKING_API_URL") ?? "http://localhost:5080"), Timeout = TimeSpan.FromSeconds(10) };
if (args.Length == 0)
{
    Console.WriteLine("Nhân viên bưu gửi — lệnh:\n  create <người gửi> <người nhận> <vị trí>\n  get <mã>\n  history <mã>\n  update <mã> <Created|InTransit|AtHub|Delivered|Failed> <vị trí> [ghi chú]\nVí dụ: create \"Nguyễn Văn Mạnh\" \"Người nhận\" \"Thái Nguyên\"");
    return;
}
try
{
    using var request = args switch
    {
        ["create", var sender, var recipient, var location] => new HttpRequestMessage(HttpMethod.Post, "/shipments")
        { Content = JsonContent.Create(new CreateShipment(sender, recipient, location), options: WireJson.Options) },
        ["get", var code] => new HttpRequestMessage(HttpMethod.Get, $"/shipments/{Uri.EscapeDataString(code)}"),
        ["history", var code] => new HttpRequestMessage(HttpMethod.Get, $"/shipments/{Uri.EscapeDataString(code)}/history"),
        ["update", var code, var status, var location, .. var rest] when Enum.TryParse<ShipmentStatus>(status, out var parsed) && Enum.IsDefined(parsed)
            => new HttpRequestMessage(HttpMethod.Post, $"/shipments/{Uri.EscapeDataString(code)}/events")
            { Content = JsonContent.Create(new AddShipmentEvent(parsed, location, string.Join(" ", rest)), options: WireJson.Options) },
        _ => throw new ArgumentException("Sai lệnh hoặc trạng thái. Chạy không có tham số để xem hướng dẫn.")
    };
    request.Headers.Add("X-Correlation-ID", Guid.NewGuid().ToString());
    if (request.Method == HttpMethod.Post)
        request.Headers.Add("Idempotency-Key", Environment.GetEnvironmentVariable("IDEMPOTENCY_KEY") ?? Guid.NewGuid().ToString());
    using var response = await http.SendAsync(request);
    Console.WriteLine($"HTTP {(int)response.StatusCode} {response.StatusCode}");
    Console.WriteLine(await response.Content.ReadAsStringAsync());
    if (!response.IsSuccessStatusCode) Environment.ExitCode = 1;
}
catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException or ArgumentException)
{
    Console.Error.WriteLine(ex.Message);
    Environment.ExitCode = 1;
}
