"use strict";
// Module-level unit tests for dist/lib. Run: node --test tests/shim
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const lib = (n) => require(path.resolve(__dirname, "..", "..", "dist", "lib", n));
const tmp = () => fs.mkdtempSync(path.join(os.tmpdir(), "questops-mod-"));

test("env: input trims and upper-cases the name; warn prefixes", (t) => {
  const { input, warn } = lib("env");
  process.env.INPUT_DATA_X = "  v ";
  assert.equal(input("data_x"), "v");
  assert.equal(input("absent-input"), "");
  const lines = [];
  t.mock.method(console, "log", (m) => lines.push(m));
  warn("hi");
  assert.deepEqual(lines, ["::warning::QuestOps: hi"]);
  delete process.env.INPUT_DATA_X;
});

test("post.remote: this repo and token by default; data-repo and data-token override them", () => {
  const { remote } = lib("post");
  const keys = ["GITHUB_SERVER_URL", "GITHUB_REPOSITORY", "INPUT_TOKEN", "INPUT_DATA-REPO", "INPUT_DATA-TOKEN"];
  const saved = Object.fromEntries(keys.map((k) => [k, process.env[k]]));
  Object.assign(process.env, { GITHUB_SERVER_URL: "https://github.com", GITHUB_REPOSITORY: "o/app", INPUT_TOKEN: "run" });
  delete process.env["INPUT_DATA-REPO"];
  delete process.env["INPUT_DATA-TOKEN"];
  assert.deepEqual(remote(), { repo: "o/app", url: "https://x-access-token:run@github.com/o/app.git" });
  process.env["INPUT_DATA-REPO"] = "o/guild";
  assert.deepEqual(remote(), { repo: "o/guild", url: "https://x-access-token:run@github.com/o/guild.git" });
  process.env["INPUT_DATA-TOKEN"] = "app";
  assert.equal(remote().url, "https://x-access-token:app@github.com/o/guild.git");
  for (const [k, v] of Object.entries(saved)) {
    if (v === undefined) delete process.env[k];
    else process.env[k] = v;
  }
});

test("stage: reset gives fresh paths and publish appends only existing files", (t) => {
  const { reset, publish } = lib("stage");
  const dir = tmp();
  const stage = path.join(dir, "stage");
  const staged = reset(stage);
  assert.equal(staged.GITHUB_OUTPUT, path.join(stage, "output"));
  fs.writeFileSync(staged.GITHUB_OUTPUT, "a=1\n");
  const target = path.join(dir, "out");
  process.env.GITHUB_OUTPUT = target;
  process.env.GITHUB_STEP_SUMMARY = path.join(dir, "sum");
  const lines = [];
  t.mock.method(console, "log", (m) => lines.push(m));
  publish(stage, { stdout: "card\n" });
  assert.deepEqual(lines, ["card"]);
  assert.equal(fs.readFileSync(target, "utf8"), "a=1\n");
  assert.equal(fs.existsSync(path.join(dir, "sum")), false);
  assert.deepEqual(Object.keys(reset(stage)).length, 3);
  assert.equal(fs.existsSync(staged.GITHUB_OUTPUT), false);
  delete process.env.GITHUB_OUTPUT;
  delete process.env.GITHUB_STEP_SUMMARY;
});
