using Tracking.Contracts;
using Tracking.Api;
using Microsoft.AspNetCore.SignalR;

var builder = WebApplication.CreateBuilder(args);
builder.Logging.ClearProviders();
builder.Logging.AddSimpleConsole(o => { o.IncludeScopes = true; o.TimestampFormat = "HH:mm:ss "; });
builder.Services.AddSingleton<ShipmentStore>();
builder.Services.AddSignalR().AddJsonProtocol(o =>
    o.PayloadSerializerOptions.Converters.Add(new System.Text.Json.Serialization.JsonStringEnumConverter<ShipmentStatus>(allowIntegerValues: false)));
builder.Services.ConfigureHttpJsonOptions(o =>
    o.SerializerOptions.Converters.Add(new System.Text.Json.Serialization.JsonStringEnumConverter<ShipmentStatus>(allowIntegerValues: false)));
var app = builder.Build();
_ = app.Services.GetRequiredService<ShipmentStore>();
app.Use(async (context, next) =>
{
    var supplied = context.Request.Headers["X-Correlation-ID"].ToString();
    var correlation = Guid.TryParse(supplied, out var id) ? id.ToString() : Guid.NewGuid().ToString();
    context.TraceIdentifier = correlation;
    context.Response.Headers["X-Correlation-ID"] = correlation;
    using var scope = app.Logger.BeginScope(new Dictionary<string, object> { ["CorrelationId"] = correlation });
    try { await next(context); }
    catch (DomainException ex) { await Results.Problem(statusCode: ex.Status, detail: ex.Message).ExecuteAsync(context); }
});
app.MapGet("/", () => Results.Ok(new { name = "Đề 08 — Hệ thống theo dõi bưu gửi", chapters = "01–03", hub = "/hubs/tracking" }));
app.MapHub<TrackingHub>("/hubs/tracking");
app.MapGet("/health/live", () => Results.Ok(new { status = "healthy" }));
app.MapGet("/health/ready", (ShipmentStore store) => store.Ready() ? Results.Ok(new { status = "ready" }) : Results.StatusCode(503));
app.MapPost("/shipments", async (CreateShipment request, ShipmentStore store, HttpContext context, IHubContext<TrackingHub> hub) =>
{
    var shipment = store.Create(request, context.Request.Headers["Idempotency-Key"].FirstOrDefault(), context.TraceIdentifier);
    app.Logger.LogInformation("Created shipment {TrackingCode}, correlation {CorrelationId}", shipment.TrackingCode, context.TraceIdentifier);
    await Notify(shipment, store, hub);
    return Results.Created($"/shipments/{shipment.TrackingCode}", shipment);
});
app.MapGet("/shipments/{trackingCode}", (string trackingCode, ShipmentStore store) =>
    store.Get(trackingCode) is { } shipment ? Results.Ok(shipment) : Results.NotFound(new { error = "Không tìm thấy bưu gửi." }));
app.MapPost("/shipments/{trackingCode}/events", async (string trackingCode, AddShipmentEvent request, ShipmentStore store, HttpContext context, IHubContext<TrackingHub> hub) =>
{
    var shipment = store.Add(trackingCode, request, context.Request.Headers["Idempotency-Key"].FirstOrDefault(), context.TraceIdentifier);
    app.Logger.LogInformation("Updated shipment {TrackingCode} to {Status}, version {Version}", trackingCode, shipment.Status, shipment.Version);
    await Notify(shipment, store, hub);
    return Results.Created($"/shipments/{trackingCode}/history", shipment);
});
app.MapGet("/shipments/{trackingCode}/history", (string trackingCode, ShipmentStore store) =>
    store.Get(trackingCode) is null ? Results.NotFound(new { error = "Không tìm thấy bưu gửi." }) : Results.Ok(store.History(trackingCode)));
app.Run();

async Task Notify(Shipment shipment, ShipmentStore store, IHubContext<TrackingHub> hub)
{
    // Chỉ phát sau khi transaction đã commit. REST history là nguồn khôi phục nếu client offline.
    try
    {
        var evt = store.Event(shipment.TrackingCode, shipment.Version);
        await hub.Clients.Group(TrackingHub.GroupName(shipment.TrackingCode)).SendAsync("ShipmentUpdated", evt);
    }
    catch (Exception ex)
    {
        app.Logger.LogWarning(ex, "Không đẩy được thông báo {TrackingCode} v{Version}; dữ liệu đã lưu, client có thể đọc lịch sử",
            shipment.TrackingCode, shipment.Version);
    }
}
