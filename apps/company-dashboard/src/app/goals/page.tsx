import { companyRepository } from "@/lib/state";
import { formatWhen, label, shortId } from "@/lib/format";
import { GoalForm } from "./goal-form";

export const dynamic = "force-dynamic";

export default async function GoalsPage() {
  const state = await companyRepository().load();
  const tasksByGoal = new Map(
    state.tasks.map((task) => [task.goalId, task] as const),
  );

  return (
    <>
      <h2>Submit a goal</h2>
      <p className="deck">
        The manager pipeline turns a goal into a bounded task, runs the policy
        and budget checks, walks the task lifecycle, and stops at a pending
        human approval. In Phase 1 this is the deterministic simulator — no
        model is called and nothing outside this dashboard changes.
      </p>
      <GoalForm />

      <h2>All goals</h2>
      {state.goals.length === 0 ? (
        <p className="deck">No goals yet.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Goal</th>
              <th>Task status</th>
              <th>Risk</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {[...state.goals].reverse().map((goal) => {
              const task = tasksByGoal.get(goal.id);
              return (
                <tr key={goal.id}>
                  <td>
                    {goal.title}
                    <div className="mono muted">{shortId(goal.id)}</div>
                  </td>
                  <td
                    className={`status status--${task?.status ?? "neutral"}`}
                  >
                    {task ? label(task.status) : "no task"}
                  </td>
                  <td className="muted">{goal.riskLevel}</td>
                  <td className="muted">{formatWhen(goal.createdAt)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </>
  );
}
