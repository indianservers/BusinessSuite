using System.Text.Json;
using Npgsql;

namespace Business_Suite;

internal sealed partial class SalesOrderRepository
{
    // Native invoice labels mirror the shared presentation catalog in backend/app/core/business_profiles.json.
    private const string InvoiceTerminologyCatalog = """{"Terms":{"customer":["Customer","Customers"],"appointment":["Appointment","Appointments"],"provider":["Service provider","Service providers"],"service":["Service","Services"],"resource":["Resource","Resources"],"project":["Project","Projects"],"employee":["Employee","Employees"]},"Profiles":{"general":{},"hospital":{"customer":["Patient","Patients"],"provider":["Doctor","Doctors"],"appointment":["Consultation","Consultations"],"service":["Consultation type","Consultation types"],"resource":["Consultation room","Consultation rooms"]},"salon":{"provider":["Stylist","Stylists"],"resource":["Chair / Room","Chairs / Rooms"]},"construction":{"customer":["Client","Clients"],"provider":["Site representative","Site representatives"],"appointment":["Site visit","Site visits"],"resource":["Site resource","Site resources"]},"accounting_firm":{"customer":["Client","Clients"],"provider":["Accountant","Accountants"],"appointment":["Consultation","Consultations"],"project":["Engagement","Engagements"]},"consulting":{"customer":["Client","Clients"],"provider":["Consultant","Consultants"],"appointment":["Consultation","Consultations"],"resource":["Meeting room","Meeting rooms"]},"repairs":{"provider":["Technician","Technicians"],"appointment":["Service visit","Service visits"]},"retail":{},"education":{"customer":["Learner","Learners"],"provider":["Instructor","Instructors"],"appointment":["Session","Sessions"],"resource":["Classroom","Classrooms"]},"pharma":{"provider":["Pharmacist","Pharmacists"],"resource":["Counter","Counters"]},"restaurant":{"customer":["Guest","Guests"],"provider":["Host","Hosts"],"appointment":["Reservation","Reservations"],"service":["Reservation type","Reservation types"],"resource":["Table","Tables"]},"manufacturing":{"customer":["Client","Clients"],"provider":["Coordinator","Coordinators"],"appointment":["Factory visit","Factory visits"],"resource":["Workstation","Workstations"]},"logistics":{"provider":["Dispatcher","Dispatchers"],"appointment":["Pickup booking","Pickup bookings"],"resource":["Vehicle","Vehicles"]},"real_estate":{"customer":["Client","Clients"],"provider":["Property advisor","Property advisors"],"appointment":["Property viewing","Property viewings"],"service":["Viewing type","Viewing types"],"resource":["Property","Properties"]},"hospitality":{"customer":["Guest","Guests"],"provider":["Concierge","Concierges"],"appointment":["Guest booking","Guest bookings"],"service":["Guest service","Guest services"],"resource":["Room","Rooms"]},"fitness":{"customer":["Member","Members"],"provider":["Trainer","Trainers"],"appointment":["Training session","Training sessions"],"service":["Training type","Training types"],"resource":["Studio","Studios"]},"legal":{"customer":["Client","Clients"],"provider":["Lawyer","Lawyers"],"appointment":["Consultation","Consultations"],"service":["Legal service","Legal services"],"resource":["Meeting room","Meeting rooms"]},"custom":{}}}""";

    private async Task<string> ResolveInvoiceTerminologyAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, int actor)
    {
        using var query = RegisterCommand(@"
            SELECT values_json::text FROM public.suite_service_policies
            WHERE organization_id=@company AND kind='business_profile'
            AND scope_key IN ('business-profile:company:'||@company,
                'business-profile:company:'||@company||':branch:'||@branch)
            ORDER BY length(scope_key)", db, tx, branch, actor);
        using var catalog = JsonDocument.Parse(InvoiceTerminologyCatalog);
        var terms = new Dictionary<string, JsonElement>();
        var overrides = new Dictionary<string, JsonElement>();
        string profile = "general";
        using (var reader = await query.ExecuteReaderAsync())
        {
            while (await reader.ReadAsync())
            {
                using var configured = JsonDocument.Parse(reader.GetString(0));
                if (configured.RootElement.TryGetProperty("business_type", out var type) &&
                    type.ValueKind == JsonValueKind.String)
                    profile = type.GetString()!;
                if (configured.RootElement.TryGetProperty("terms", out var labels) &&
                    labels.ValueKind == JsonValueKind.Object)
                    foreach (var label in labels.EnumerateObject())
                        overrides[label.Name] = label.Value.Clone();
            }
        }
        foreach (var label in catalog.RootElement.GetProperty("Terms").EnumerateObject())
            terms[label.Name] = label.Value;
        if (catalog.RootElement.GetProperty("Profiles").TryGetProperty(profile, out var profileTerms))
            foreach (var label in profileTerms.EnumerateObject())
                terms[label.Name] = label.Value;
        foreach (var label in overrides)
            terms[label.Key] = label.Value;
        return JsonSerializer.Serialize(terms);
    }
}
