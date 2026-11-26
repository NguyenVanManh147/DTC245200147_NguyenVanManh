using var http = new HttpClient { BaseAddress = new Uri(Environment.GetEnvironmentVariable("TRACKING_API_URL") ?? "http://localhost:5080"), Timeout = TimeSpan.FromSeconds(10) };
Console.WriteLine(await http.GetStringAsync("/"));
