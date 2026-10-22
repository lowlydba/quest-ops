"use strict";
const { env, input } = require("./env");

// Conclusion of every step that has finished so far in *this* job.
// continue-on-error steps report "success" here, matching job.status semantics.
async function listJobs() {
  const url = `${env.GITHUB_API_URL}/repos/${env.GITHUB_REPOSITORY}/actions/runs/${env.GITHUB_RUN_ID}/attempts/${env.GITHUB_RUN_ATTEMPT || 1}/jobs?per_page=100`;
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${input("token")}`, Accept: "application/vnd.github+json" },
  });
  if (!res.ok) throw new Error(`jobs API returned ${res.status} (does the token have actions: read?)`);
  return (await res.json()).jobs;
}

// The jobs API can lag the runner by tens of seconds when many jobs start together: a job that has only just
// started may still read as queued with no runner, and a step that has only just failed may still read as
// running. Both are retried for about a minute (only while unsettled, so the usual case never waits); our own post step
// (and the post steps queued behind it) are the only steps allowed to be unfinished.
const unfinished = (job) => job.steps.filter((s) => s.status !== "completed" && !/^Post /.test(s.name));

async function jobOutcome() {
  const attempts = 12;
  let jobs, me;
  for (let n = 1; n <= attempts; n++) {
    jobs = await listJobs();
    me = jobs.filter((j) => j.status === "in_progress" && j.runner_name === env.RUNNER_NAME);
    if (n === attempts || me.length > 1 || (me.length === 1 && unfinished(me[0]).length === 0)) break;
    await new Promise((resolve) => setTimeout(resolve, Number(env.QUESTOPS_JOB_RETRY_MS || 5000)));
  }
  if (me.length !== 1) {
    const seen = jobs.map((j) => `${j.name}:${j.status}:${j.runner_name}`).join(", ");
    throw new Error(`could not identify the current job (${me.length} candidates for runner "${env.RUNNER_NAME}"; API shows: ${seen || "no jobs"})`);
  }
  const done = me[0].steps.map((s) => s.conclusion).filter(Boolean);
  if (done.includes("cancelled")) return "cancelled";
  if (done.includes("failure")) return "failure";
  return "success";
}

module.exports = { listJobs, jobOutcome, unfinished };
