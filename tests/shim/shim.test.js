"use strict";
// Unit and integration tests for dist/index.js. Run: node --test tests/shim
const test = require("node:test");
const assert = require("node:assert/strict");
const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const shimPath = path.resolve(__dirname, "..", "..", "dist", "index.js");
const shim = require(shimPath);
const hasBash = spawnSync("bash", ["--version"], { stdio: "ignore" }).status === 0;
const needsBash = hasBash && process.platform !== "win32" ? {} : { skip: "needs bash and a POSIX runner" };

// The suite may itself run inside GitHub Actions, so strip every variable the shim reads.
const scoped = /^(INPUT_|GITHUB_|RUNNER_|STATE_|QUESTOPS_)/;
const baseEnv = Object.fromEntries(Object.entries(process.env).filter(([k]) => !scoped.test(k)));
const tmp = () => fs.mkdtempSync(path.join(os.tmpdir(), "questops-shim-"));

function resetEnv(extra = {}) {
  for (const k of Object.keys(process.env)) delete process.env[k];
  Object.assign(process.env, baseEnv, extra);
}

function capture(t) {
  const lines = [];
  t.mock.method(console, "log", (m) => lines.push(String(m)));
  return lines;
}

function mockJobs(t, jobs, status = 200) {
  const calls = [];
  t.mock.method(globalThis, "fetch", async (url, opts) => {
    calls.push({ url, opts });
    return { ok: status === 200, status, json: async () => ({ jobs }) };
  });
  return calls;
}

const job = (conclusions, over = {}) => ({
  status: "in_progress",
  runner_name: "runner-1",
  steps: conclusions.map((conclusion) => ({ conclusion, status: "completed", name: "step" })),
  ...over,
});

const apiEnv = {
  GITHUB_API_URL: "https://api.example.test",
  GITHUB_REPOSITORY: "o/r",
  GITHUB_RUN_ID: "42",
  RUNNER_NAME: "runner-1",
  INPUT_TOKEN: "tok",
};

test.beforeEach(() => resetEnv());
test.after(() => resetEnv());

test("jobOutcome reads the current job by runner name and sends the token", async (t) => {
  resetEnv({ ...apiEnv, GITHUB_RUN_ATTEMPT: "3" });
  const calls = mockJobs(t, [job(["success", null]), job(["failure"], { runner_name: "other" })]);
  assert.equal(await shim.jobOutcome(), "success");
  assert.equal(calls[0].url, "https://api.example.test/repos/o/r/actions/runs/42/attempts/3/jobs?per_page=100");
  assert.match(calls[0].opts.headers.Authorization, /tok$/);
});

test("jobOutcome defaults to attempt 1", async (t) => {
  resetEnv(apiEnv);
  const calls = mockJobs(t, [job([])]);
  assert.equal(await shim.jobOutcome(), "success");
  assert.match(calls[0].url, /attempts\/1\/jobs/);
});

test("jobOutcome reports failure and prefers cancelled", async (t) => {
  resetEnv(apiEnv);
  mockJobs(t, [job(["success", "failure"])]);
  assert.equal(await shim.jobOutcome(), "failure");
  t.mock.restoreAll();
  mockJobs(t, [job(["failure", "cancelled"])]);
  assert.equal(await shim.jobOutcome(), "cancelled");
});

test("jobOutcome ignores finished jobs and fails on zero or several candidates", async (t) => {
  resetEnv({ ...apiEnv, QUESTOPS_JOB_RETRY_MS: "1" });
  const calls = mockJobs(t, [job(["success"], { status: "completed", name: "build" })]);
  await assert.rejects(shim.jobOutcome(), /0 candidates for runner "runner-1"; API shows: build:completed:runner-1/);
  assert.equal(calls.length, 12);
  t.mock.restoreAll();
  mockJobs(t, [job([]), job([])]);
  await assert.rejects(shim.jobOutcome(), /2 candidates/);
  t.mock.restoreAll();
  mockJobs(t, []);
  await assert.rejects(shim.jobOutcome(), /API shows: no jobs/);
});

test("jobOutcome waits for a step the API still shows as running, but not for post steps", async (t) => {
  resetEnv({ ...apiEnv, QUESTOPS_JOB_RETRY_MS: "1" });
  const post = { name: "Post Run $/", status: "in_progress", conclusion: null };
  const lagging = { name: "Run exit 1", status: "in_progress", conclusion: null };
  const settled = { name: "Run exit 1", status: "completed", conclusion: "failure" };
  let call = 0;
  t.mock.method(globalThis, "fetch", async () => ({
    ok: true,
    status: 200,
    json: async () => ({ jobs: [job([], { steps: [++call < 3 ? lagging : settled, post] })] }),
  }));
  assert.equal(await shim.jobOutcome(), "failure");
  assert.equal(call, 3);
});

test("jobOutcome gives up waiting on a step that never settles and reads what it has", async (t) => {
  resetEnv({ ...apiEnv, QUESTOPS_JOB_RETRY_MS: "1" });
  const calls = mockJobs(t, [job([], { steps: [{ name: "Run x", status: "in_progress", conclusion: null }] })]);
  assert.equal(await shim.jobOutcome(), "success");
  assert.equal(calls.length, 12);
});

test("jobOutcome retries while the API has not caught up, using the default delay", async (t) => {
  resetEnv(apiEnv);
  let call = 0;
  const delays = [];
  t.mock.method(globalThis, "setTimeout", (fn, ms) => {
    delays.push(ms);
    fn();
  });
  t.mock.method(globalThis, "fetch", async () => ({
    ok: true,
    status: 200,
    json: async () => ({ jobs: ++call < 2 ? [] : [job(["failure"])] }),
  }));
  assert.equal(await shim.jobOutcome(), "failure");
  assert.equal(call, 2);
  assert.deepEqual(delays, [5000]);
});

test("jobOutcome explains a rejected token", async (t) => {
  resetEnv(apiEnv);
  mockJobs(t, [], 403);
  await assert.rejects(shim.jobOutcome(), /403.*actions: read/);
});

test("python finds an interpreter, and throws when none is on PATH", () => {
  assert.match(shim.python(), /^python3?$/);
  process.env.PATH = "";
  assert.throws(() => shim.python(), /python3 not found/);
});

test("main arms the hook on the first call with an omen picked by the run", async (t) => {
  const lines = capture(t);
  const state = path.join(tmp(), "state");
  resetEnv({ GITHUB_STATE: state, GITHUB_RUN_ID: "12345" });
  await shim.main();
  assert.equal(fs.readFileSync(state, "utf8"), "questopsPost=true\n");
  assert.equal(lines[0], shim.omen("12345"));
  assert.ok(shim.OMENS.some((o) => lines[0] === `QuestOps: ${o}`));
});

test("omens are stable per run, all reachable, and all say the job decides", () => {
  assert.equal(shim.omen("42"), shim.omen("42"));
  const seen = new Set(Array.from({ length: 200 }, (_, i) => shim.omen(String(i))));
  assert.equal(seen.size, shim.OMENS.length);
  assert.ok(shim.OMENS.every((o) => /job/.test(o)));
  resetEnv();
  assert.equal(shim.omen(), shim.omen(""));
});

test("bots get a merchant omen, never a monster", () => {
  assert.ok(shim.isBot("dependabot[bot]") && shim.isBot(" Renovate ") && shim.isBot("github-actions"));
  assert.ok(!shim.isBot("octocat") && !shim.isBot(undefined));
  const seen = new Set(Array.from({ length: 200 }, (_, i) => shim.omen(String(i), true)));
  assert.equal(seen.size, shim.BOT_OMENS.length);
  assert.ok(shim.BOT_OMENS.every((o) => /job/.test(o) && !/monster/i.test(o)));
  resetEnv({ INPUT_PLAYER: "dependabot[bot]" });
  assert.ok(shim.BOT_OMENS.some((o) => shim.omen("7") === `QuestOps: ${o}`));
  resetEnv({ GITHUB_ACTOR: "octocat" });
  assert.ok(shim.OMENS.some((o) => shim.omen("7") === `QuestOps: ${o}`));
});

test("post skips the encounter when the job result cannot be read", async (t) => {
  const lines = capture(t);
  resetEnv(apiEnv);
  mockJobs(t, [], 500);
  await shim.post();
  assert.match(lines.join("\n"), /::warning::QuestOps: jobs API returned 500.*skipping the encounter/);
});

test("post auto-detects the outcome and plays a dry run", async (t) => {
  const lines = capture(t);
  resetEnv({ ...apiEnv, INPUT_OUTCOME: "auto", INPUT_PERSIST: "false", INPUT_SEED: "shim", INPUT_PLAYER: "tester", RUNNER_TEMP: tmp() });
  mockJobs(t, [job(["failure"])]);
  await shim.post();
  assert.equal(lines.filter((l) => l.startsWith("::warning::")).length, 0);
});

test("post skips ignored players without reading the job or playing", async (t) => {
  const lines = capture(t);
  resetEnv({ ...apiEnv, INPUT_PLAYER: "Dependabot[bot]", INPUT_IGNORE: "octocat, *[bot]", RUNNER_TEMP: tmp() });
  mockJobs(t, [], 500);
  await shim.post();
  assert.deepEqual(lines, ["QuestOps: Dependabot[bot] is on the ignore list. The dungeon pretends not to notice."]);
});

test("post plays players who are not on the ignore list", async (t) => {
  const lines = capture(t);
  resetEnv({ ...apiEnv, INPUT_PLAYER: "tester", INPUT_IGNORE: "octocat *[bot]", INPUT_OUTCOME: "success", INPUT_PERSIST: "false", INPUT_SEED: "shim", RUNNER_TEMP: tmp() });
  await shim.post();
  assert.ok(!lines.join("\n").includes("ignore list"));
});

function prEnv(extra = {}) {
  const dir = tmp();
  const event = path.join(dir, "event.json");
  fs.writeFileSync(event, JSON.stringify({ pull_request: { number: 7 } }));
  return {
    ...apiEnv,
    GITHUB_EVENT_NAME: "pull_request",
    GITHUB_WORKFLOW: "ci",
    GITHUB_JOB: "play",
    GITHUB_EVENT_PATH: event,
    INPUT_PLAYER: "tester",
    INPUT_OUTCOME: "success",
    INPUT_PERSIST: "false",
    INPUT_SEED: "shim",
    INPUT_COMMENT: "true",
    RUNNER_TEMP: tmp(),
    ...extra,
  };
}

// A fake issues API holding `comments`; records every call.
const BOT = { type: "Bot" };

function mockComments(t, comments, failWith = 0) {
  const calls = [];
  t.mock.method(globalThis, "fetch", async (url, opts = {}) => {
    const method = opts.method || "GET";
    calls.push({ url, method, body: opts.body && JSON.parse(opts.body) });
    if (failWith) return { ok: false, status: failWith, json: async () => ({}) };
    return { ok: true, status: 200, json: async () => (method === "GET" ? comments : {}) };
  });
  return calls;
}

test("summary: false keeps the encounter out of the job summary but not the comment", async (t) => {
  capture(t);
  const summary = path.join(tmp(), "summary.md");
  resetEnv(prEnv({ GITHUB_STEP_SUMMARY: summary, INPUT_SUMMARY: "false" }));
  const calls = mockComments(t, []);
  await shim.post();
  assert.ok(!fs.existsSync(summary));
  assert.equal(calls.length, 2);
  resetEnv(prEnv({ GITHUB_STEP_SUMMARY: summary }));
  mockComments(t, []);
  await shim.post();
  assert.match(fs.readFileSync(summary, "utf8"), /QuestOps/);
});

test("comment posts the encounter on the pull request once", async (t) => {
  capture(t);
  resetEnv(prEnv());
  const calls = mockComments(t, [{ id: 1, body: "someone else's comment" }]);
  await shim.post();
  assert.deepEqual(calls.map((c) => c.method), ["GET", "POST"]);
  assert.equal(calls[1].url, "https://api.example.test/repos/o/r/issues/7/comments");
  assert.match(calls[1].body.body, /^<!-- questops:sticky:ci:play -->\n.*tester/s);
});

test("comment edits its own earlier comment instead of adding another", async (t) => {
  capture(t);
  resetEnv(prEnv());
  const calls = mockComments(t, [{ id: 5, user: BOT, body: "<!-- questops:sticky:ci:play -->\nold encounter" }]);
  await shim.post();
  assert.deepEqual(calls.map((c) => c.method), ["GET", "PATCH"]);
  assert.equal(calls[1].url, "https://api.example.test/repos/o/r/issues/comments/5");
  assert.ok(!calls[1].body.body.includes("old encounter"));
});

test("comment ignores a human's copy of the marker", async (t) => {
  capture(t);
  resetEnv(prEnv());
  const calls = mockComments(t, [{ id: 3, user: { type: "User" }, body: "<!-- questops:sticky:ci:play -->\nspoof" }]);
  await shim.post();
  assert.deepEqual(calls.map((c) => c.method), ["GET", "POST"]);
});

test("workflows and jobs on one pull request each keep their own comment", async (t) => {
  capture(t);
  const others = [
    { id: 1, user: BOT, body: "<!-- questops:sticky:other:play -->\nanother workflow" },
    { id: 2, user: BOT, body: "<!-- questops:sticky:ci:other -->\nanother job" },
  ];
  resetEnv(prEnv());
  let calls = mockComments(t, others);
  await shim.post();
  assert.deepEqual(calls.map((c) => c.method), ["GET", "POST"]);
  resetEnv(prEnv({ GITHUB_JOB: "other" }));
  calls = mockComments(t, others);
  await shim.post();
  assert.deepEqual(calls.map((c) => [c.method, c.url.split("/").pop()]), [["GET", "comments?per_page=100&page=1"], ["PATCH", "2"]]);
});

test("comment pages through a busy pull request to find its comment", async (t) => {
  capture(t);
  resetEnv(prEnv());
  const pages = [Array.from({ length: 100 }, (_, i) => ({ id: i, body: "x" })), [{ id: 900, user: BOT, body: "<!-- questops:sticky:ci:play -->" }]];
  const calls = [];
  t.mock.method(globalThis, "fetch", async (url, opts = {}) => {
    calls.push({ url, method: opts.method || "GET" });
    return { ok: true, status: 200, json: async () => (calls.length <= 2 ? pages[calls.length - 1] : {}) };
  });
  await shim.post();
  assert.deepEqual(calls.map((c) => c.method), ["GET", "GET", "PATCH"]);
  assert.match(calls[2].url, /comments\/900$/);
});

test("comment does nothing by default, outside pull requests, or without a summary to post", async (t) => {
  const lines = capture(t);
  resetEnv(prEnv({ INPUT_COMMENT: "" }));
  let calls = mockComments(t, []);
  await shim.post();
  assert.equal(calls.length, 0);

  resetEnv(prEnv({ GITHUB_EVENT_NAME: "push" }));
  calls = mockComments(t, []);
  await shim.post();
  assert.equal(calls.length, 0);
  assert.match(lines.join("\n"), /comment is on, but this is not a pull request event/);

  resetEnv(prEnv({ INPUT_IGNORE: "tester" }));
  calls = mockComments(t, []);
  await shim.post();
  assert.equal(calls.length, 0);
});

test("comment finds the pull request from the ref when the event file is unreadable", async (t) => {
  capture(t);
  resetEnv(prEnv({ GITHUB_EVENT_PATH: "/nonexistent", GITHUB_REF: "refs/pull/12/merge" }));
  const calls = mockComments(t, []);
  await shim.post();
  assert.equal(calls[1].url, "https://api.example.test/repos/o/r/issues/12/comments");
});

test("comment gives up quietly when no pull request number can be found", async (t) => {
  const lines = capture(t);
  const event = path.join(tmp(), "event.json");
  fs.writeFileSync(event, "{}");
  for (const extra of [{ GITHUB_EVENT_PATH: event }, { GITHUB_EVENT_PATH: event, GITHUB_REF: "refs/heads/main" }, { GITHUB_EVENT_NAME: undefined }]) {
    resetEnv(prEnv(extra));
    const calls = mockComments(t, []);
    await shim.post();
    assert.equal(calls.length, 0);
  }
  assert.equal(lines.filter((l) => /not a pull request event/.test(l)).length, 3);
});

test("comment skips runs that played nothing", async (t) => {
  capture(t);
  resetEnv(prEnv({ INPUT_OUTCOME: "cancelled" }));
  const calls = mockComments(t, []);
  await shim.post();
  assert.equal(calls.length, 0);
});

test("comment failures warn and never fail the job", async (t) => {
  const lines = capture(t);
  resetEnv(prEnv());
  mockComments(t, [], 403);
  await shim.post();
  assert.match(lines.join("\n"), /::warning::QuestOps: could not comment on the pull request: GET .* returned 403.*pull-requests: write/);
});

test("post warns when the encounter itself fails", async (t) => {
  const lines = capture(t);
  resetEnv({ INPUT_OUTCOME: "success", INPUT_PERSIST: "false", INPUT_KIND: "bogus", RUNNER_TEMP: tmp() });
  await shim.post();
  assert.match(lines.join("\n"), /encounter exited with 2/);
});

// A throwaway "GitHub": a bare repo reachable over a file:// URL, which the shim builds from
// GITHUB_SERVER_URL and GITHUB_REPOSITORY just like it does for https.
function fakeGithub() {
  const root = tmp();
  const bare = path.join(root, "o", "r.git");
  fs.mkdirSync(bare, { recursive: true });
  spawnSync("git", ["init", "--bare", "--quiet", bare]);
  const env = {
    GITHUB_SERVER_URL: `file://${root}`,
    GITHUB_REPOSITORY: "o/r",
    GITHUB_ACTOR: "tester",
    RUNNER_TEMP: path.join(root, "runner"),
    QUESTOPS_RETRY_DELAY_MS: "1",
    INPUT_OUTCOME: "success",
    INPUT_SEED: "shim",
    INPUT_TOKEN: "tok",
  };
  fs.mkdirSync(env.RUNNER_TEMP);
  return { root, bare, env };
}

const remoteFile = (bare, file) =>
  spawnSync("git", ["--git-dir", bare, "show", `questops-data:${file}`], { encoding: "utf8" });

function rejectPushes(bare, marker) {
  const hook = path.join(bare, "hooks", "pre-receive");
  const body = marker
    ? `#!/bin/sh\nif [ ! -e "${marker}" ]; then touch "${marker}"; echo "rejected: raced" >&2; exit 1; fi\n`
    : `#!/bin/sh\necho "rejected: raced" >&2\nexit 1\n`;
  fs.writeFileSync(hook, body, { mode: 0o755 });
}

test("post persists the hero to the data branch", needsBash, async (t) => {
  capture(t);
  const gh = fakeGithub();
  resetEnv(gh.env);
  await shim.post();
  const sheet = remoteFile(gh.bare, "characters/tester.json");
  assert.equal(sheet.status, 0, sheet.stderr);
  assert.equal(remoteFile(gh.bare, "log/quests.jsonl").status, 0);
});

test("post writes to another repository's data branch when data-repo is set", needsBash, async (t) => {
  capture(t);
  const gh = fakeGithub();
  const guild = path.join(gh.root, "o", "guild.git");
  spawnSync("git", ["init", "--bare", "--quiet", guild]);
  const summary = path.join(gh.root, "summary.md");
  resetEnv({ ...gh.env, "INPUT_DATA-REPO": "o/guild", GITHUB_STEP_SUMMARY: summary });
  await shim.post();
  assert.equal(remoteFile(guild, "characters/tester.json").status, 0);
  assert.notEqual(remoteFile(gh.bare, "characters/tester.json").status, 0);
});

for (const outcome of ["cancelled", "skipped"]) {
  test(`post does not push a ${outcome} run`, needsBash, async (t) => {
    capture(t);
    const gh = fakeGithub();
    resetEnv({ ...gh.env, INPUT_OUTCOME: outcome });
    await shim.post();
    assert.notEqual(remoteFile(gh.bare, "characters/tester.json").status, 0);
  });
}

test("post redoes the quest after losing the push race, and reports only the attempt that sticks", needsBash, async (t) => {
  const lines = capture(t);
  const gh = fakeGithub();
  rejectPushes(gh.bare, path.join(gh.root, "marker"));
  const summary = path.join(gh.root, "summary.md");
  const output = path.join(gh.root, "output.txt");
  resetEnv({ ...gh.env, GITHUB_STEP_SUMMARY: summary, GITHUB_OUTPUT: output });
  await shim.post();
  const out = lines.join("\n");
  assert.match(out, /another run pushed first; trying again in 1 ms \(1\/9\)/);
  assert.equal(out.match(/VICTORY/g).length, 1);
  assert.equal(fs.readFileSync(summary, "utf8").match(/## .* QuestOps:/g).length, 1);
  assert.equal(fs.readFileSync(output, "utf8").match(/^encounter=/gm).length, 1);
  assert.equal(remoteFile(gh.bare, "characters/tester.json").status, 0);
});

test("post backs off with jitter when no delay override is set", needsBash, async (t) => {
  const lines = capture(t);
  const gh = fakeGithub();
  rejectPushes(gh.bare, path.join(gh.root, "marker"));
  const { QUESTOPS_RETRY_DELAY_MS, ...env } = gh.env;
  resetEnv(env);
  const waits = [];
  t.mock.method(globalThis, "setTimeout", (fn, ms) => {
    waits.push(ms);
    fn();
  });
  await shim.post();
  assert.equal(waits.length, 1);
  assert.ok(waits[0] >= 500 && waits[0] < 2000, `waited ${waits[0]} ms`);
  assert.match(lines.join("\n"), new RegExp(`trying again in ${waits[0]} ms`));
});

test("post gives up after repeated races", needsBash, async (t) => {
  const lines = capture(t);
  const gh = fakeGithub();
  rejectPushes(gh.bare);
  resetEnv(gh.env);
  await shim.post();
  const out = lines.join("\n");
  assert.match(out, /\(9\/9\)/);
  assert.match(out, /::warning::QuestOps: gave up after repeated races/);
});

test("post warns when the push fails for another reason", needsBash, async (t) => {
  const lines = capture(t);
  const gh = fakeGithub();
  fs.rmSync(gh.bare, { recursive: true, force: true });
  resetEnv(gh.env);
  await shim.post();
  assert.match(lines.join("\n"), /could not push the data branch/);
});

test("post warns when the data branch cannot be fetched", needsBash, async (t) => {
  const lines = capture(t);
  const gh = fakeGithub();
  const blocker = path.join(gh.root, "blocker");
  fs.writeFileSync(blocker, "");
  resetEnv({ ...gh.env, RUNNER_TEMP: blocker });
  await shim.post();
  assert.match(lines.join("\n"), /could not fetch the data branch/);
});

test("post warns when the persisted encounter fails", needsBash, async (t) => {
  const lines = capture(t);
  const gh = fakeGithub();
  resetEnv({ ...gh.env, INPUT_KIND: "bogus", GITHUB_OUTPUT: path.join(gh.root, "output.txt") });
  await shim.post();
  assert.match(lines.join("\n"), /encounter exited with 2/);
});

test("running the file as a script arms, then plays, and never throws", () => {
  const state = path.join(tmp(), "state");
  const env = { ...baseEnv, GITHUB_STATE: state };
  const first = spawnSync(process.execPath, [shimPath], { env, encoding: "utf8" });
  assert.equal(first.status, 0);
  assert.ok(first.stdout.startsWith("QuestOps: "));
  const second = spawnSync(process.execPath, [shimPath], {
    env: { ...env, STATE_questopsPost: "true", INPUT_OUTCOME: "success", INPUT_PERSIST: "false", INPUT_KIND: "bogus", RUNNER_TEMP: tmp() },
    encoding: "utf8",
  });
  assert.equal(second.status, 0);
  assert.match(second.stdout, /::warning::/);
});

test("the script reports a missing GITHUB_STATE as a warning, not a crash", () => {
  const r = spawnSync(process.execPath, [shimPath], { env: { ...baseEnv }, encoding: "utf8" });
  assert.equal(r.status, 0);
  assert.match(r.stdout, /::warning::QuestOps:/);
});
