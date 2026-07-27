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
      <h2>Lifecycle test lab</h2>
      <p className="deck">
        Exercise the deterministic lifecycle without calling a model or
        changing the repository. To send real work to the automated workers,
        use the CEO page.
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
