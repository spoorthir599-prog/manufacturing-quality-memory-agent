import { useEffect, useMemo, useState } from "react";

const API_URL = "http://localhost:5000";

const statusColors = {
  Open: "bg-rose-50 text-rose-700",
  "Under Investigation": "bg-amber-50 text-amber-700",
  Resolved: "bg-emerald-50 text-emerald-700",
};

const severityColors = {
  Critical: "bg-rose-100 text-rose-700",
  High: "bg-orange-100 text-orange-700",
  Medium: "bg-amber-100 text-amber-700",
  Low: "bg-slate-100 text-slate-600",
};

function App() {
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState("");
  const [activePage, setActivePage] = useState("Dashboard");
  const [search, setSearch] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [saving, setSaving] = useState(false);

  const [formData, setFormData] = useState({
    part: "",
    defect: "",
    severity: "Medium",
    cause: "",
    action: "",
  });

  // Load incidents from Express/MySQL
  async function loadIncidents() {
    try {
      setLoading(true);
      setApiError("");

      const response = await fetch(`${API_URL}/api/incidents`);

      if (!response.ok) {
        throw new Error(`Could not load incidents (HTTP ${response.status})`);
      }

      const data = await response.json();
      const incidents = Array.isArray(data.items) ? data.items : [];

      const formattedRecords = incidents.map((incident) => ({
        id: incident.incident_code || `QIR-${incident.id}`,
        backendId: incident.id,
        part: incident.description || "Unspecified product",
        defect: incident.title || "Untitled defect",
        severity: incident.severity || "Medium",
        status: incident.status || "Open",
        date: incident.created_at
          ? String(incident.created_at).slice(0, 10)
          : "",
        cause: incident.root_cause || "",
        action: incident.corrective_action || "",
      }));

      setRecords(formattedRecords);
    } catch (error) {
      console.error("Failed to load incidents:", error);
      setApiError(
        error.message ||
          "Unable to connect to the Express backend at localhost:5000."
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadIncidents();
  }, []);

  const filteredRecords = useMemo(() => {
    const query = search.toLowerCase().trim();

    if (!query) return records;

    return records.filter((record) =>
      Object.values(record).some((value) =>
        String(value ?? "").toLowerCase().includes(query)
      )
    );
  }, [records, search]);

  const openCount = records.filter((record) => record.status === "Open").length;

  const investigationCount = records.filter(
    (record) => record.status === "Under Investigation"
  ).length;

  const resolvedCount = records.filter(
    (record) => record.status === "Resolved"
  ).length;

  // Create a new incident through Express API
  async function addRecord(event) {
    event.preventDefault();
    setApiError("");
    setSaving(true);

    const incidentCode = `QIR-${Date.now()}`;

    try {
      const response = await fetch(`${API_URL}/api/incidents`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          incident_code: incidentCode,
          title: formData.defect.trim(),
          description: formData.part.trim(),
          defect_category: "Manufacturing Defect",
          severity: formData.severity,
          status: "Open",
          root_cause: formData.cause.trim(),
          corrective_action: formData.action.trim(),
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(
          `Could not save defect (HTTP ${response.status}): ${errorText}`
        );
      }

      const savedIncident = await response.json();

      const newRecord = {
        id: savedIncident.incident_code || incidentCode,
        backendId: savedIncident.id,
        part: formData.part.trim(),
        defect: formData.defect.trim(),
        severity: formData.severity,
        status: "Open",
        date: new Date().toISOString().slice(0, 10),
        cause: formData.cause.trim(),
        action: formData.action.trim(),
      };

      setRecords((current) => [newRecord, ...current]);

      setFormData({
        part: "",
        defect: "",
        severity: "Medium",
        cause: "",
        action: "",
      });

      setShowForm(false);
      setActivePage("Defect Records");
    } catch (error) {
      console.error("Error saving defect:", error);
      setApiError(error.message || "Something went wrong while saving.");
    } finally {
      setSaving(false);
    }
  }

  // Status changes are currently local to the browser
  function updateStatus(id, status) {
    setRecords((current) =>
      current.map((record) =>
        record.id === id ? { ...record, status } : record
      )
    );

    setSelectedRecord((current) =>
      current?.id === id ? { ...current, status } : current
    );
  }

  const navigation = [
    { name: "Dashboard", icon: "▦" },
    { name: "Defect Records", icon: "▤" },
    { name: "AI Memory Search", icon: "⌕" },
    { name: "Corrective Actions", icon: "✓" },
  ];

  const kpis = [
    {
      label: "Total Defects",
      value: records.length,
      description: "All recorded quality events",
      icon: "▤",
      color: "bg-blue-50 text-blue-700",
    },
    {
      label: "Open Issues",
      value: openCount,
      description: "Require attention",
      icon: "!",
      color: "bg-rose-50 text-rose-700",
    },
    {
      label: "Under Investigation",
      value: investigationCount,
      description: "Root cause analysis ongoing",
      icon: "⌕",
      color: "bg-amber-50 text-amber-700",
    },
    {
      label: "Resolved",
      value: resolvedCount,
      description: "Corrective action completed",
      icon: "✓",
      color: "bg-emerald-50 text-emerald-700",
    },
  ];

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      {/* Sidebar */}
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-64 flex-col border-r border-slate-200 bg-white md:flex">
        <div className="flex h-20 items-center gap-3 border-b border-slate-100 px-6">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-700 text-xl font-bold text-white">
            Q
          </div>

          <div>
            <h1 className="font-bold tracking-tight text-slate-900">
              Quality Memory
            </h1>
            <p className="text-xs text-slate-500">Manufacturing Agent</p>
          </div>
        </div>

        <div className="px-4 py-6">
          <p className="mb-3 px-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
            Workspace
          </p>

          <nav className="space-y-1">
            {navigation.map((item) => (
              <button
                key={item.name}
                onClick={() => {
                  setActivePage(item.name);
                  setSelectedRecord(null);
                }}
                className={`flex w-full items-center gap-3 rounded-lg px-3 py-3 text-left text-sm font-medium transition ${
                  activePage === item.name
                    ? "bg-blue-50 text-blue-700"
                    : "text-slate-600 hover:bg-slate-50"
                }`}
              >
                <span className="w-5 text-center text-lg">{item.icon}</span>
                {item.name}
              </button>
            ))}
          </nav>
        </div>

        <div className="mt-auto border-t border-slate-100 p-4">
          <div className="rounded-xl bg-slate-50 p-4">
            <p className="text-sm font-semibold text-slate-700">
              Quality knowledge base
            </p>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              Search historical defects, root causes, and corrective actions.
            </p>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="md:pl-64">
        <header className="sticky top-0 z-10 flex h-20 items-center justify-between border-b border-slate-200 bg-white/95 px-5 backdrop-blur sm:px-8">
          <div>
            <p className="text-xs font-medium text-slate-500">
              Manufacturing / Quality
            </p>
            <h2 className="text-lg font-bold text-slate-900">{activePage}</h2>
          </div>

          <div className="flex items-center gap-3">
            <div className="hidden text-right sm:block">
              <p className="text-sm font-semibold">Quality Team</p>
              <p className="text-xs text-slate-500">Manufacturing</p>
            </div>
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-100 font-bold text-blue-700">
              QT
            </div>
          </div>
        </header>

        <div className="mx-auto max-w-7xl space-y-6 p-5 sm:p-8">
          {loading && (
            <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-800">
              Loading incidents from the backend...
            </div>
          )}

          {apiError && (
            <div
              role="alert"
              className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800"
            >
              Backend error: {apiError}. Confirm the Express server is running
              at http://localhost:5000.
            </div>
          )}

          {/* Dashboard */}
          {activePage === "Dashboard" && (
            <>
              <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
                <div>
                  <h3 className="text-2xl font-bold tracking-tight text-slate-900">
                    Quality overview
                  </h3>
                  <p className="mt-1 text-sm text-slate-500">
                    Track manufacturing defects and learn from past quality
                    events.
                  </p>
                </div>

                <button
                  onClick={() => setShowForm(true)}
                  className="rounded-lg bg-blue-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-800"
                >
                  + Add defect record
                </button>
              </div>

              <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                {kpis.map((kpi) => (
                  <div
                    key={kpi.label}
                    className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
                  >
                    <div className="flex items-start justify-between">
                      <p className="text-sm font-medium text-slate-500">
                        {kpi.label}
                      </p>
                      <span
                        className={`flex h-9 w-9 items-center justify-center rounded-lg text-lg font-bold ${kpi.color}`}
                      >
                        {kpi.icon}
                      </span>
                    </div>

                    <p className="mt-4 text-3xl font-bold text-slate-900">
                      {kpi.value}
                    </p>
                    <p className="mt-1 text-xs text-slate-500">
                      {kpi.description}
                    </p>
                  </div>
                ))}
              </section>

              <section className="grid gap-6 xl:grid-cols-3">
                <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm xl:col-span-2">
                  <div className="mb-5 flex items-center justify-between">
                    <div>
                      <h4 className="font-bold text-slate-900">
                        Recent defect records
                      </h4>
                      <p className="mt-1 text-sm text-slate-500">
                        Latest quality events entered into the system
                      </p>
                    </div>

                    <button
                      onClick={() => setActivePage("Defect Records")}
                      className="text-sm font-semibold text-blue-700 hover:text-blue-900"
                    >
                      View all
                    </button>
                  </div>

                  <div className="space-y-3">
                    {records.slice(0, 4).map((record) => (
                      <button
                        key={record.id}
                        onClick={() => setSelectedRecord(record)}
                        className="flex w-full flex-col gap-3 rounded-lg border border-slate-100 p-4 text-left hover:border-blue-200 hover:bg-blue-50/40 sm:flex-row sm:items-center sm:justify-between"
                      >
                        <div>
                          <p className="text-xs font-semibold text-blue-700">
                            {record.id}
                          </p>
                          <p className="mt-1 font-semibold text-slate-800">
                            {record.defect}
                          </p>
                          <p className="mt-1 text-sm text-slate-500">
                            {record.part}
                          </p>
                        </div>

                        <span
                          className={`w-fit rounded-full px-3 py-1 text-xs font-semibold ${
                            statusColors[record.status] ||
                            "bg-slate-100 text-slate-600"
                          }`}
                        >
                          {record.status}
                        </span>
                      </button>
                    ))}

                    {records.length === 0 && !loading && (
                      <p className="py-8 text-center text-sm text-slate-500">
                        No incidents have been recorded yet.
                      </p>
                    )}
                  </div>
                </div>

                <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                  <h4 className="font-bold text-slate-900">
                    AI Memory Search
                  </h4>
                  <p className="mt-2 text-sm leading-6 text-slate-500">
                    Find similar defects and review previously recorded causes
                    and corrective actions.
                  </p>

                  <button
                    onClick={() => setActivePage("AI Memory Search")}
                    className="mt-5 w-full rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm font-semibold text-blue-700 hover:bg-blue-100"
                  >
                    Search quality memory →
                  </button>

                  <div className="mt-5 rounded-lg bg-slate-50 p-4">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Example search
                    </p>
                    <p className="mt-2 text-sm text-slate-700">
                      “Find previous cases of surface cracks”
                    </p>
                  </div>
                </div>
              </section>
            </>
          )}

          {/* Defect records */}
          {activePage === "Defect Records" && (
            <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
              <div className="flex flex-col justify-between gap-4 border-b border-slate-100 p-5 sm:flex-row sm:items-center">
                <div>
                  <h3 className="font-bold text-slate-900">Defect records</h3>
                  <p className="mt-1 text-sm text-slate-500">
                    Browse and inspect recorded quality issues.
                  </p>
                </div>

                <button
                  onClick={() => setShowForm(true)}
                  className="rounded-lg bg-blue-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-800"
                >
                  + Add defect
                </button>
              </div>

              <div className="p-5">
                <input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search part, defect, cause, status..."
                  className="mb-4 w-full rounded-lg border border-slate-300 px-4 py-3 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                />

                <div className="overflow-x-auto">
                  <table className="w-full min-w-[700px] text-left text-sm">
                    <thead>
                      <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                        <th className="px-3 py-3 font-semibold">Record ID</th>
                        <th className="px-3 py-3 font-semibold">
                          Part / Product
                        </th>
                        <th className="px-3 py-3 font-semibold">Defect</th>
                        <th className="px-3 py-3 font-semibold">Severity</th>
                        <th className="px-3 py-3 font-semibold">Status</th>
                        <th className="px-3 py-3 font-semibold">Details</th>
                      </tr>
                    </thead>

                    <tbody>
                      {filteredRecords.map((record) => (
                        <tr
                          key={record.id}
                          className="border-b border-slate-100 hover:bg-slate-50"
                        >
                          <td className="px-3 py-4 font-semibold text-blue-700">
                            {record.id}
                          </td>
                          <td className="px-3 py-4 font-medium">
                            {record.part}
                          </td>
                          <td className="px-3 py-4">{record.defect}</td>
                          <td className="px-3 py-4">
                            <span
                              className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                                severityColors[record.severity] ||
                                "bg-slate-100 text-slate-600"
                              }`}
                            >
                              {record.severity}
                            </span>
                          </td>
                          <td className="px-3 py-4">
                            <span
                              className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                                statusColors[record.status] ||
                                "bg-slate-100 text-slate-600"
                              }`}
                            >
                              {record.status}
                            </span>
                          </td>
                          <td className="px-3 py-4">
                            <button
                              onClick={() => setSelectedRecord(record)}
                              className="font-semibold text-blue-700 hover:underline"
                            >
                              View details
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>

                  {filteredRecords.length === 0 && (
                    <p className="py-10 text-center text-sm text-slate-500">
                      No matching defect records found.
                    </p>
                  )}
                </div>
              </div>
            </section>
          )}

          {/* AI Memory Search */}
          {activePage === "AI Memory Search" && (
            <section className="mx-auto max-w-3xl rounded-xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-50 text-3xl text-blue-700">
                ⌕
              </div>

              <h3 className="mt-4 text-center text-xl font-bold text-slate-900">
                Search quality memory
              </h3>

              <p className="mx-auto mt-2 max-w-xl text-center text-sm leading-6 text-slate-500">
                Search the incident records currently loaded from MySQL. This
                is keyword matching in the browser, not yet an AI-powered
                semantic search.
              </p>

              <div className="mt-6 flex flex-col gap-2 sm:flex-row">
                <input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Try: heat treatment, cracks, tool wear..."
                  className="min-w-0 flex-1 rounded-lg border border-slate-300 px-4 py-3 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                />

                <button
                  onClick={() => setSearch("")}
                  className="rounded-lg border border-slate-300 px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                >
                  Clear
                </button>
              </div>

              <div className="mt-6 space-y-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Matching records ({filteredRecords.length})
                </p>

                {filteredRecords.map((record) => (
                  <button
                    key={record.id}
                    onClick={() => setSelectedRecord(record)}
                    className="w-full rounded-lg border border-slate-200 p-4 text-left hover:border-blue-300 hover:bg-blue-50/40"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-xs font-semibold text-blue-700">
                        {record.id} · {record.part}
                      </span>
                      <span
                        className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                          statusColors[record.status] ||
                          "bg-slate-100 text-slate-600"
                        }`}
                      >
                        {record.status}
                      </span>
                    </div>

                    <p className="mt-2 font-semibold text-slate-800">
                      {record.defect}
                    </p>
                    <p className="mt-2 text-sm text-slate-600">
                      <strong>Root cause:</strong>{" "}
                      {record.cause || "Not recorded"}
                    </p>
                    <p className="mt-1 text-sm text-slate-600">
                      <strong>Action:</strong>{" "}
                      {record.action || "Not recorded"}
                    </p>
                  </button>
                ))}

                {filteredRecords.length === 0 && (
                  <p className="rounded-lg bg-slate-50 p-6 text-center text-sm text-slate-500">
                    No matching records. Try another keyword.
                  </p>
                )}
              </div>
            </section>
          )}

          {/* Corrective actions */}
          {activePage === "Corrective Actions" && (
            <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="font-bold text-slate-900">Corrective actions</h3>
              <p className="mt-1 text-sm text-slate-500">
                Review actions associated with defect records and update their
                status.
              </p>

              <div className="mt-5 space-y-3">
                {records.map((record) => (
                  <div
                    key={record.id}
                    className="rounded-lg border border-slate-200 p-4"
                  >
                    <div className="flex flex-col justify-between gap-3 sm:flex-row">
                      <div>
                        <p className="text-xs font-semibold text-blue-700">
                          {record.id} · {record.part}
                        </p>
                        <p className="mt-1 font-semibold">{record.defect}</p>
                        <p className="mt-2 text-sm text-slate-600">
                          {record.action || "No corrective action recorded."}
                        </p>
                      </div>

                      <select
                        value={record.status}
                        onChange={(event) =>
                          updateStatus(record.id, event.target.value)
                        }
                        className="h-10 rounded-lg border border-slate-300 bg-white px-3 text-sm"
                        aria-label={`Update status for ${record.id}`}
                      >
                        <option>Open</option>
                        <option>Under Investigation</option>
                        <option>Resolved</option>
                      </select>
                    </div>
                  </div>
                ))}

                {records.length === 0 && (
                  <p className="py-8 text-center text-sm text-slate-500">
                    No corrective actions to display.
                  </p>
                )}
              </div>
            </section>
          )}
        </div>
      </main>

      {/* Add defect modal */}
      {showForm && (
        <div className="fixed inset-0 z-30 flex items-center justify-center bg-slate-900/50 p-4">
          <form
            onSubmit={addRecord}
            className="max-h-[90vh] w-full max-w-lg space-y-4 overflow-y-auto rounded-2xl bg-white p-6 shadow-xl"
          >
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-slate-900">
                Add defect record
              </h3>

              <button
                type="button"
                onClick={() => setShowForm(false)}
                className="rounded-lg px-3 py-1 text-xl text-slate-500 hover:bg-slate-100"
                aria-label="Close form"
              >
                ×
              </button>
            </div>

            {[
              {
                label: "Part / Product",
                key: "part",
                placeholder: "Enter part name",
              },
              {
                label: "Defect description",
                key: "defect",
                placeholder: "Describe the defect",
              },
              {
                label: "Root cause",
                key: "cause",
                placeholder: "Enter known or suspected cause",
              },
              {
                label: "Corrective action",
                key: "action",
                placeholder: "Enter corrective action",
              },
            ].map((field) => (
              <label key={field.key} className="block">
                <span className="mb-1.5 block text-sm font-medium text-slate-700">
                  {field.label}
                </span>

                <input
                  required
                  value={formData[field.key]}
                  onChange={(event) =>
                    setFormData((current) => ({
                      ...current,
                      [field.key]: event.target.value,
                    }))
                  }
                  placeholder={field.placeholder}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                />
              </label>
            ))}

            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-slate-700">
                Severity
              </span>

              <select
                value={formData.severity}
                onChange={(event) =>
                  setFormData((current) => ({
                    ...current,
                    severity: event.target.value,
                  }))
                }
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm"
              >
                <option>Low</option>
                <option>Medium</option>
                <option>High</option>
                <option>Critical</option>
              </select>
            </label>

            {apiError && (
              <p className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">
                {apiError}
              </p>
            )}

            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setShowForm(false)}
                className="rounded-lg border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>

              <button
                type="submit"
                disabled={saving}
                className="rounded-lg bg-blue-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {saving ? "Saving..." : "Save defect"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Record details modal */}
      {selectedRecord && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-semibold text-blue-700">
                  {selectedRecord.id}
                </p>
                <h3 className="mt-1 text-xl font-bold text-slate-900">
                  {selectedRecord.defect}
                </h3>
                <p className="mt-1 text-sm text-slate-500">
                  {selectedRecord.part}
                </p>
              </div>

              <button
                onClick={() => setSelectedRecord(null)}
                className="rounded-lg px-3 py-1 text-xl text-slate-500 hover:bg-slate-100"
                aria-label="Close details"
              >
                ×
              </button>
            </div>

            <div className="mt-5 space-y-4 text-sm">
              <div>
                <p className="font-semibold text-slate-500">Root cause</p>
                <p className="mt-1 text-slate-800">
                  {selectedRecord.cause || "Not recorded"}
                </p>
              </div>

              <div>
                <p className="font-semibold text-slate-500">
                  Corrective action
                </p>
                <p className="mt-1 text-slate-800">
                  {selectedRecord.action || "Not recorded"}
                </p>
              </div>

              <div className="flex flex-wrap gap-2">
                <span
                  className={`rounded-full px-3 py-1 text-xs font-semibold ${
                    severityColors[selectedRecord.severity] ||
                    "bg-slate-100 text-slate-600"
                  }`}
                >
                  {selectedRecord.severity} severity
                </span>

                <span
                  className={`rounded-full px-3 py-1 text-xs font-semibold ${
                    statusColors[selectedRecord.status] ||
                    "bg-slate-100 text-slate-600"
                  }`}
                >
                  {selectedRecord.status}
                </span>
              </div>
            </div>

            <button
              onClick={() => setSelectedRecord(null)}
              className="mt-6 w-full rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800"
            >
              Close details
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;