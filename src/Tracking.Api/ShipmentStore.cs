using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Microsoft.Data.Sqlite;
using Tracking.Contracts;

namespace Tracking.Api;

public sealed class DomainException(int status, string message) : Exception(message)
{
    public int Status { get; } = status;
}

public sealed class ShipmentStore
{
    private readonly string connectionString;
    private readonly object gate = new();

    public ShipmentStore(IConfiguration config)
    {
        var path = Path.GetFullPath(config["Storage:Path"] ?? "data/tracking.db");
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        connectionString = new SqliteConnectionStringBuilder { DataSource = path, DefaultTimeout = 10 }.ToString();
        using var db = Open();
        using var command = db.CreateCommand();
        command.CommandText = """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS shipments (code TEXT PRIMARY KEY, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, code TEXT NOT NULL, version INTEGER NOT NULL,
                body TEXT NOT NULL, UNIQUE(code, version));
            CREATE TABLE IF NOT EXISTS requests (key TEXT PRIMARY KEY, hash TEXT NOT NULL, body TEXT NOT NULL);
            """;
        command.ExecuteNonQuery();
    }

    private SqliteConnection Open()
    {
        var db = new SqliteConnection(connectionString);
        db.Open();
        return db;
    }

    private static SqliteCommand Command(SqliteConnection db, string sql, params (string, object?)[] values)
    {
        var command = db.CreateCommand();
        command.CommandText = sql;
        foreach (var (name, value) in values) command.Parameters.AddWithValue(name, value ?? DBNull.Value);
        return command;
    }

    public Shipment? Get(string code)
    {
        using var db = Open();
        using var command = Command(db, "SELECT body FROM shipments WHERE code=$code", ("$code", code));
        return command.ExecuteScalar() is string body ? JsonSerializer.Deserialize<Shipment>(body, WireJson.Options) : null;
    }

    public List<ShipmentEvent> History(string code)
    {
        using var db = Open();
        using var command = Command(db, "SELECT body FROM events WHERE code=$code ORDER BY version", ("$code", code));
        using var reader = command.ExecuteReader();
        var result = new List<ShipmentEvent>();
        while (reader.Read()) result.Add(JsonSerializer.Deserialize<ShipmentEvent>(reader.GetString(0), WireJson.Options)!);
        return result;
    }

    public Shipment Create(CreateShipment request, string? key, string correlationId) => Mutate(
        "create", request, key, correlationId, () =>
        {
            ValidateText(request.Sender, "Người gửi");
            ValidateText(request.Recipient, "Người nhận");
            ValidateText(request.Location, "Vị trí");
            var now = DateTimeOffset.UtcNow;
            return new Shipment("BG" + Guid.NewGuid().ToString("N").ToUpperInvariant(), request.Sender.Trim(),
                request.Recipient.Trim(), request.Location.Trim(), ShipmentStatus.Created, now, now, 1);
        }, null);

    public Shipment Add(string code, AddShipmentEvent request, string? key, string correlationId) => Mutate(
        "event:" + code, request, key, correlationId, () =>
        {
            ValidateText(request.Location, "Vị trí");
            if (request.Note?.Length > 1000) throw new DomainException(400, "Ghi chú tối đa 1000 ký tự.");
            if (!Enum.IsDefined(request.Status)) throw new DomainException(400, "Trạng thái không hợp lệ.");
            var old = Get(code) ?? throw new DomainException(404, "Không tìm thấy bưu gửi.");
            if (!ShipmentRules.CanTransition(old.Status, request.Status))
                throw new DomainException(409, $"Không thể chuyển từ {old.Status} sang {request.Status}.");
            return old with { Location = request.Location.Trim(), Status = request.Status,
                UpdatedAt = DateTimeOffset.UtcNow, Version = old.Version + 1 };
        }, request.Note);

    private Shipment Mutate<T>(string scope, T request, string? key, string correlationId, Func<Shipment> factory, string? note)
    {
        if (key?.Length > 100 || key is not null && string.IsNullOrWhiteSpace(key))
            throw new DomainException(400, "Idempotency-Key phải có 1–100 ký tự.");
        var hash = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(scope + JsonSerializer.Serialize(request, WireJson.Options))));
        lock (gate)
        {
            using var db = Open();
            using var tx = db.BeginTransaction();
            if (key is not null)
            {
                using var lookup = Command(db, "SELECT hash,body FROM requests WHERE key=$key", ("$key", key));
                lookup.Transaction = tx;
                using var reader = lookup.ExecuteReader();
                if (reader.Read())
                {
                    if (reader.GetString(0) != hash) throw new DomainException(409, "Idempotency-Key đã dùng với yêu cầu khác.");
                    return JsonSerializer.Deserialize<Shipment>(reader.GetString(1), WireJson.Options)!;
                }
            }
            var shipment = factory();
            var body = JsonSerializer.Serialize(shipment, WireJson.Options);
            var evt = new ShipmentEvent(Guid.NewGuid(), shipment.TrackingCode, shipment.Status, shipment.Location,
                shipment.UpdatedAt, note, shipment.Version, correlationId);
            using (var save = Command(db, "INSERT INTO shipments(code,body) VALUES($code,$body) ON CONFLICT(code) DO UPDATE SET body=$body",
                ("$code", shipment.TrackingCode), ("$body", body)))
            { save.Transaction = tx; save.ExecuteNonQuery(); }
            using (var save = Command(db, "INSERT INTO events(id,code,version,body) VALUES($id,$code,$version,$body)",
                ("$id", evt.EventId.ToString()), ("$code", evt.TrackingCode), ("$version", evt.Version),
                ("$body", JsonSerializer.Serialize(evt, WireJson.Options))))
            { save.Transaction = tx; save.ExecuteNonQuery(); }
            if (key is not null)
            {
                using var save = Command(db, "INSERT INTO requests(key,hash,body) VALUES($key,$hash,$body)",
                    ("$key", key), ("$hash", hash), ("$body", body));
                save.Transaction = tx; save.ExecuteNonQuery();
            }
            tx.Commit();
            return shipment;
        }
    }

    public ShipmentEvent Event(string code, long version)
    {
        using var db = Open();
        using var cmd = Command(db, "SELECT body FROM events WHERE code=$code AND version=$version", ("$code", code), ("$version", version));
        return JsonSerializer.Deserialize<ShipmentEvent>((string)cmd.ExecuteScalar()!, WireJson.Options)!;
    }

    public bool Ready()
    {
        using var db = Open();
        using var command = Command(db, "SELECT 1");
        return Convert.ToInt32(command.ExecuteScalar()) == 1;
    }

    private static void ValidateText(string? text, string field)
    {
        if (string.IsNullOrWhiteSpace(text) || text.Length > 200)
            throw new DomainException(400, $"{field} phải có 1–200 ký tự.");
    }
}
