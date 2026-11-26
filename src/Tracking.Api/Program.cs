using Tracking.Contracts;
using Tracking.Api;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddSingleton<ShipmentStore>();
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
app.MapGet("/", () => Results.Ok(new { name = "Parcel Tracking API", chapter = 2 }));
app.MapGet("/health/live", () => Results.Ok(new { status = "healthy" }));
app.MapGet("/health/ready", (ShipmentStore store) => store.Ready() ? Results.Ok(new { status = "ready" }) : Results.StatusCode(503));
app.MapPost("/shipments", (CreateShipment request, ShipmentStore store, HttpContext context) =>
{
    var shipment = store.Create(request, context.Request.Headers["Idempotency-Key"].FirstOrDefault(), context.TraceIdentifier);
    app.Logger.LogInformation("Created shipment {TrackingCode}, correlation {CorrelationId}", shipment.TrackingCode, context.TraceIdentifier);
    return Results.Created($"/shipments/{shipment.TrackingCode}", shipment);
});
app.MapGet("/shipments/{trackingCode}", (string trackingCode, ShipmentStore store) =>
    store.Get(trackingCode) is { } shipment ? Results.Ok(shipment) : Results.NotFound(new { error = "Không tìm thấy bưu gửi." }));
app.MapPost("/shipments/{trackingCode}/events", (string trackingCode, AddShipmentEvent request, ShipmentStore store, HttpContext context) =>
{
    var shipment = store.Add(trackingCode, request, context.Request.Headers["Idempotency-Key"].FirstOrDefault(), context.TraceIdentifier);
    app.Logger.LogInformation("Updated shipment {TrackingCode} to {Status}, version {Version}", trackingCode, shipment.Status, shipment.Version);
    return Results.Created($"/shipments/{trackingCode}/history", shipment);
});
app.MapGet("/shipments/{trackingCode}/history", (string trackingCode, ShipmentStore store) =>
    store.Get(trackingCode) is null ? Results.NotFound(new { error = "Không tìm thấy bưu gửi." }) : Results.Ok(store.History(trackingCode)));
app.Run();
