using Notification.Service;
using Tracking.Contracts;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddSignalR().AddJsonProtocol(o =>
    o.PayloadSerializerOptions.Converters.Add(new System.Text.Json.Serialization.JsonStringEnumConverter<ShipmentStatus>(allowIntegerValues: false)));
var app = builder.Build();
app.MapGet("/health/live", () => Results.Ok(new { status = "healthy" }));
app.MapHub<TrackingHub>("/hubs/tracking");
app.Run();
