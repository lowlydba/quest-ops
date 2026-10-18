"use strict";
const fs = require("fs");
const { env, input, log, warn } = require("./env");

// Marks the one comment per workflow and job on a pull request that every run edits instead of adding another,
// so workflows that all fire on the same pull request never overwrite each other.
const marker = () => `<!-- questops:sticky:${env.GITHUB_WORKFLOW}:${env.GITHUB_JOB} -->`;

function prNumber() {
  if (!/^pull_request(_target)?$/.test(env.GITHUB_EVENT_NAME)) return 0;
  try {
    const n = JSON.parse(fs.readFileSync(env.GITHUB_EVENT_PATH, "utf8")).pull_request?.number;
    if (n) return n;
  } catch {
    // fall back to the ref, which reads refs/pull/<n>/merge on these events
  }
  const ref = /^refs\/pull\/(\d+)\//.exec(env.GITHUB_REF);
  return ref ? Number(ref[1]) : 0;
}

async function api(method, url, body) {
  const res = await fetch(url, {
    method,
    headers: { Authorization: `Bearer ${input("token")}`, Accept: "application/vnd.github+json", "Content-Type": "application/json" },
    body: body && JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${method} ${new URL(url).pathname} returned ${res.status}`);
  return res.json();
}

async function findSticky(base, number) {
  for (let page = 1; ; page++) {
    const comments = await api("GET", `${base}/${number}/comments?per_page=100&page=${page}`);
    const mine = comments.find((c) => c.user?.type === "Bot" && c.body.startsWith(marker()));
    if (mine || comments.length < 100) return mine;
  }
}

// Posts the encounter on the pull request, or edits the comment an earlier run left there.
// Failing to comment never fails the job.
async function sticky(summary) {
  const number = prNumber();
  if (!number) return log("QuestOps: comment is on, but this is not a pull request event. No comment posted.");
  const base = `${env.GITHUB_API_URL}/repos/${env.GITHUB_REPOSITORY}/issues`;
  const body = `${marker()}\n${summary.trim()}\n`;
  try {
    const existing = await findSticky(base, number);
    if (existing) await api("PATCH", `${base}/comments/${existing.id}`, { body });
    else await api("POST", `${base}/${number}/comments`, { body });
  } catch (e) {
    warn(`could not comment on the pull request: ${e.message} (needs pull-requests: write, and pull requests from forks get a read-only token).`);
  }
}

module.exports = { sticky, prNumber, marker };
