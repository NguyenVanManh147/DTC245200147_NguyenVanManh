using System.Text;
using Customer.Client;

Console.OutputEncoding = Encoding.UTF8;
Console.InputEncoding = Encoding.UTF8;
using var stop = new CancellationTokenSource();
Console.CancelKeyPress += (_, e) => { e.Cancel = true; stop.Cancel(); };
await using var session = new CustomerSession(Environment.GetEnvironmentVariable("TRACKING_API_URL") ?? "http://localhost:5080", stop.Token);
try
{
    if (args.Length > 0)
    {
        foreach (var code in args.Distinct(StringComparer.OrdinalIgnoreCase)) await session.Watch(code);
        ConsoleView.Message("Đang theo dõi; Ctrl+C để thoát.");
        await Task.WhenAny(session.Disconnected, Task.Delay(Timeout.Infinite, stop.Token));
        if (!stop.IsCancellationRequested) Environment.ExitCode = 1;
        return;
    }
    while (!stop.IsCancellationRequested)
    {
        ConsoleView.Message("\nKHÁCH HÀNG BƯU GỬI\n1. Tra cứu bưu gửi\n2. Xem lịch sử hành trình\n3. Đăng ký theo dõi bưu gửi\n4. Hủy theo dõi bưu gửi\n5. Xem các mã đang theo dõi\n0. Thoát");
        var choice = await ConsoleView.Read("Chọn: ", stop.Token);
        if (choice is null or "0") break;
        try
        {
            switch (choice)
            {
                case "1": await session.Show(await ConsoleView.Read("Mã bưu gửi: ", stop.Token) ?? "", false); break;
                case "2": await session.Show(await ConsoleView.Read("Mã bưu gửi: ", stop.Token) ?? "", true); break;
                case "3": await session.Watch(await ConsoleView.Read("Mã bưu gửi: ", stop.Token) ?? ""); break;
                case "4": await session.Unwatch(await ConsoleView.Read("Mã bưu gửi: ", stop.Token) ?? ""); break;
                case "5": session.ListWatched(); break;
                default: ConsoleView.Message("Lựa chọn không hợp lệ. Vui lòng chọn 0–5."); break;
            }
        }
        catch (Exception ex) when (!stop.IsCancellationRequested) { ConsoleView.Message("Không thực hiện được: " + ex.Message); }
    }
}
catch (OperationCanceledException) when (stop.IsCancellationRequested) { }
catch (Exception ex) { ConsoleView.Message("Không thực hiện được: " + ex.Message); Environment.ExitCode = 1; }
finally { stop.Cancel(); }
ConsoleView.Message("Đã thoát ứng dụng khách hàng.");
