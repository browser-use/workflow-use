export async function fetchWorkflowLogs(taskId: string, position: number) {
  const res = await fetch(
    `http://127.0.0.1:8000/api/workflows/logs/${taskId}?position=${position}`
  );

  if (!res.ok) throw new Error(`Failed to fetch logs (${res.status})`);

  return await res.json(); // { logs: string[], log_position: number, status: string, error?: string }
}

export async function cancelWorkflow(taskId: string) {
  const res = await fetch(
    `http://127.0.0.1:8000/api/workflows/tasks/${taskId}/cancel`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    }
  );

  const data = await res.json();

  if (!res.ok || !data.success) {
    throw new Error(data.message || 'Failed to cancel workflow');
  }

  return data;
}
