import { useEffect, useState } from "react";
import { LeadAnalytics, errorMessage, leadsApi } from "./api";

export function LeadAnalyticsPanel({
  owners,
  revision,
}: {
  owners: { id: number; name: string }[];
  revision: number;
}) {
  const [data, setData] = useState<LeadAnalytics>();
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    leadsApi
      .analytics()
      .then((response) => {
        if (active) setData(response.data);
      })
      .catch((error) => {
        if (active) setError(errorMessage(error));
      });
    return () => {
      active = false;
    };
  }, [revision]);
  if (error)
    return (
      <p role="alert" className="lm-error">
        {error}
      </p>
    );
  if (!data) return <p role="status">Loading lead performance…</p>;
  return (
    <section className="lm-performance">
      <header>
        <h2>Lead performance</h2>
        <p>
          {data.scope} · {data.leadCount} records
          {data.truncated ? " · limited to the newest 5,000 records" : ""}
        </p>
      </header>
      <div className="lm-form-grid">
        <div>
          <h3>Recorded stage progression</h3>
          <div className="lm-table-scroll">
            <table className="lm-table">
              <thead>
                <tr>
                  <th>Stage</th>
                  <th>Leads reached</th>
                  <th>Average hours before exit</th>
                </tr>
              </thead>
              <tbody>
                {data.stageHistory.map((stage) => (
                  <tr key={stage.stage}>
                    <td>{stage.stage}</td>
                    <td>{stage.leadsEverInStage}</td>
                    <td>
                      {stage.averageHoursBeforeExit === null
                        ? "No timed exits"
                        : `${stage.averageHoursBeforeExit}h (${stage.timedExits} exits)`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <div>
          <h3>Salesperson performance</h3>
          <div className="lm-table-scroll">
            <table className="lm-table">
              <thead>
                <tr>
                  <th>Owner</th>
                  <th>Qualified / total</th>
                  <th>Converted</th>
                  <th>First response</th>
                </tr>
              </thead>
              <tbody>
                {data.byOwner.map((owner) => (
                  <tr key={owner.key}>
                    <td>
                      {owners.find((o) => o.id === Number(owner.key))?.name ||
                        (owner.key === "unassigned"
                          ? "Unassigned"
                          : `User ${owner.key}`)}
                    </td>
                    <td>
                      {owner.qualified} / {owner.leads}
                    </td>
                    <td>{owner.conversionRate}%</td>
                    <td>
                      {owner.averageFirstResponseMinutes === null
                        ? "Not recorded"
                        : `${owner.averageFirstResponseMinutes} min (${owner.responseSampleSize} leads)`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
      <p className="lm-help">{data.measurementNote}</p>
    </section>
  );
}
