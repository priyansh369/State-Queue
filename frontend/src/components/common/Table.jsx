export default function Table({ columns, data, rowKey, className = "" }) {
  return (
    <table className={`table ${className}`.trim()}>
      <thead>
        <tr>
          {columns.map((col) => (
            <th key={col.key}>{col.title}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {data.map((row) => (
          <tr
            key={row[rowKey] || row.id}
            data-priority={row.priority}
            data-status={row.status}
            data-escalation={row.escalation_required ? "true" : "false"}
          >
            {columns.map((col) => (
              <td key={col.key}>
                {col.render ? col.render(row[col.dataIndex], row) : row[col.dataIndex]}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

