using System.Text.Json;
using System.Text.Json.Serialization;

namespace Tracking.Contracts;

public enum ShipmentStatus { Created, InTransit, AtHub, Delivered, Failed }
public sealed record CreateShipment(string Sender, string Recipient, string Location);
public sealed record AddShipmentEvent(ShipmentStatus Status, string Location, string? Note = null);
public sealed record Shipment(string TrackingCode, string Sender, string Recipient,
    string Location, ShipmentStatus Status, DateTimeOffset CreatedAt, DateTimeOffset UpdatedAt, long Version);
public sealed record ShipmentEvent(Guid EventId, string TrackingCode, ShipmentStatus Status,
    string Location, DateTimeOffset OccurredAt, string? Note, long Version, string CorrelationId);

public static class WireJson
{
    public static readonly JsonSerializerOptions Options = new(JsonSerializerDefaults.Web)
    {
        Converters = { new JsonStringEnumConverter<ShipmentStatus>(allowIntegerValues: false) }
    };
}

public static class ShipmentRules
{
    public static bool CanTransition(ShipmentStatus from, ShipmentStatus to) => (from, to) switch
    {
        (ShipmentStatus.Created, ShipmentStatus.InTransit or ShipmentStatus.AtHub or ShipmentStatus.Failed) => true,
        (ShipmentStatus.InTransit, ShipmentStatus.AtHub or ShipmentStatus.Delivered or ShipmentStatus.Failed) => true,
        (ShipmentStatus.AtHub, ShipmentStatus.InTransit or ShipmentStatus.Delivered or ShipmentStatus.Failed) => true,
        (ShipmentStatus.Failed, ShipmentStatus.InTransit or ShipmentStatus.AtHub) => true,
        _ => false
    };
}
