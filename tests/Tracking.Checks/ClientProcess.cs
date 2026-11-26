using System.Collections.Concurrent;
using System.Diagnostics;
using System.Text;

// Chạy đúng Console App người dùng sử dụng, điều khiển stdin/stdout để kiểm tra menu thật.
internal sealed class ClientProcess : IAsyncDisposable
{
    private readonly Process process;
    private readonly ConcurrentQueue<string> lines = new();
    public string Output => string.Join('\n', lines);
    public bool Has(string text) => Output.Contains(text, StringComparison.Ordinal);
    public int Count(string text) => lines.Count(x => x.Contains(text, StringComparison.Ordinal));

    public ClientProcess(string root, string configuration, string project, string address, params string[] args)
    {
        var start = new ProcessStartInfo("dotnet")
        {
            WorkingDirectory = root, UseShellExecute = false, CreateNoWindow = true,
            RedirectStandardInput = true, RedirectStandardOutput = true, RedirectStandardError = true,
            StandardInputEncoding = new UTF8Encoding(false), StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8
        };
        start.ArgumentList.Add(Path.Combine(root, "src", project, "bin", configuration, "net10.0", project + ".dll"));
        foreach (var arg in args) start.ArgumentList.Add(arg);
        start.Environment["TRACKING_API_URL"] = address;
        process = Process.Start(start) ?? throw new InvalidOperationException("Không chạy được " + project);
        process.OutputDataReceived += (_, e) => { if (e.Data is not null) lines.Enqueue(e.Data); };
        process.ErrorDataReceived += (_, e) => { if (e.Data is not null) lines.Enqueue(e.Data); };
        process.BeginOutputReadLine();
        process.BeginErrorReadLine();
    }

    public async Task Input(params string[] input)
    {
        foreach (var value in input) await process.StandardInput.WriteLineAsync(value);
        await process.StandardInput.FlushAsync();
    }

    public async Task WaitFor(string text, int seconds = 15)
    {
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(seconds));
        try
        {
            while (!Has(text))
            {
                if (process.HasExited) throw new InvalidOperationException("Client dừng trước khi có: " + text + "\n" + Output);
                await Task.Delay(30, timeout.Token);
            }
        }
        catch (OperationCanceledException) { throw new TimeoutException("Chưa nhận: " + text + "\n" + Output); }
    }

    public async Task<int> Exit()
    {
        await process.WaitForExitAsync().WaitAsync(TimeSpan.FromSeconds(15));
        process.WaitForExit(); // Đợi các callback đọc stdout hoàn tất.
        return process.ExitCode;
    }

    public async ValueTask DisposeAsync()
    {
        if (!process.HasExited) { process.Kill(entireProcessTree: true); await process.WaitForExitAsync(); }
        process.Dispose();
    }
}
