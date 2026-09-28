import { useEffect, useState } from "react";
import {
  fetchCustomerServiceQueries,
  resolveCustomerServiceQuery,
} from "../api";

export default function CustomerService() {
  const [queries, setQueries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [resolving, setResolving] = useState(null);
  const [filter, setFilter] = useState("pending");

  async function loadQueries() {
    try {
      setError("");

      const data = await fetchCustomerServiceQueries();

      setQueries(
        Array.isArray(data) ? data : []
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadQueries();
  }, []);

  async function handleResolve(queryId) {
    const confirmed = window.confirm(
      `Mark Customer Service query ${queryId} as resolved?`
    );

    if (!confirmed) {
      return;
    }

    try {
      setResolving(queryId);
      setError("");

      await resolveCustomerServiceQuery(queryId);

      await loadQueries();
    } catch (err) {
      setError(err.message);
    } finally {
      setResolving(null);
    }
  }

  const pendingCount = queries.filter(
    (query) =>
      String(query.status || "").toLowerCase() === "pending"
  ).length;

  const resolvedCount = queries.filter(
    (query) =>
      String(query.status || "").toLowerCase() === "resolved"
  ).length;

  const filteredQueries = queries.filter((query) => {
    const status = String(
      query.status || ""
    ).toLowerCase();

    if (filter === "all") {
      return true;
    }

    return status === filter;
  });

  return (
    <section>
      <div className="pageTitle">
        <span className="eyebrow">
          CUSTOMER SUPPORT
        </span>

        <h1>Customer Service</h1>

        <p>
          Review and resolve customer queries that require
          manual investigation.
        </p>
      </div>

      {!loading && !error && (
        <div className="customerServiceSummary">
          <button
            className={
              filter === "pending"
                ? "customerFilter active"
                : "customerFilter"
            }
            onClick={() => setFilter("pending")}
          >
            Pending
            <b>{pendingCount}</b>
          </button>

          <button
            className={
              filter === "resolved"
                ? "customerFilter active"
                : "customerFilter"
            }
            onClick={() => setFilter("resolved")}
          >
            Resolved
            <b>{resolvedCount}</b>
          </button>

          <button
            className={
              filter === "all"
                ? "customerFilter active"
                : "customerFilter"
            }
            onClick={() => setFilter("all")}
          >
            All
            <b>{queries.length}</b>
          </button>
        </div>
      )}

      {loading && (
        <div className="panel empty">
          Loading customer queries...
        </div>
      )}

      {error && (
        <div className="panel empty">
          Error: {error}
        </div>
      )}

      {!loading &&
        !error &&
        filteredQueries.length === 0 && (
          <div className="panel empty">
            {filter === "pending"
              ? "No pending customer queries."
              : filter === "resolved"
              ? "No resolved customer queries."
              : "No customer queries found."}
          </div>
        )}

      {!loading &&
        !error &&
        filteredQueries.length > 0 && (
          <div className="approvalList">
            {filteredQueries.map((query) => {
              const isResolved =
                String(
                  query.status || ""
                ).toLowerCase() === "resolved";

              return (
                <article
                  className="panel approvalCard"
                  key={query.query_id}
                >
                  <div className="approvalHead">
                    <div>
                      <span className="eyebrow">
                        {query.query_type ||
                          "CUSTOMER QUERY"}
                      </span>

                      <h2>{query.subject}</h2>

                      <p>
                        <strong>From:</strong>{" "}
                        {query.sender_email ||
                          "Unknown sender"}
                      </p>
                    </div>

                    <span
                      className={
                        isResolved
                          ? "customerStatus resolved"
                          : "customerStatus pendingStatus"
                      }
                    >
                      {isResolved
                        ? "Resolved"
                        : "Pending"}
                    </span>
                  </div>

                  <div className="facts">
                    <div>
                      <span>Query ID</span>
                      <b>{query.query_id}</b>
                    </div>

                    <div>
                      <span>Assigned Team</span>
                      <b>
                        {query.assigned_team ||
                          "Customer Service"}
                      </b>
                    </div>

                    <div>
                      <span>Customer</span>
                      <b>
                        {query.detected_customer_name ||
                          "New / Unknown"}
                      </b>
                    </div>

                    <div>
                      <span>
                        {isResolved
                          ? "Resolved"
                          : "Received"}
                      </span>

                      <b>
                        {isResolved &&
                        query.resolved_at
                          ? new Date(
                              query.resolved_at
                            ).toLocaleString()
                          : query.created_at
                          ? new Date(
                              query.created_at
                            ).toLocaleString()
                          : "-"}
                      </b>
                    </div>
                  </div>

                  <p className="diag">
                    <b>Customer Message</b>
                    {query.body}
                  </p>

                  {!isResolved && (
                    <div className="actions">
                      <button
                        className="approve"
                        disabled={
                          resolving === query.query_id
                        }
                        onClick={() =>
                          handleResolve(
                            query.query_id
                          )
                        }
                      >
                        {resolving === query.query_id
                          ? "Resolving..."
                          : "✓ Resolve"}
                      </button>
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        )}
    </section>
  );
}