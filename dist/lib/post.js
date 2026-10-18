"use strict";
const path = require("path");
const { env, input, log, warn, run } = require("./env");
const { jobOutcome } = require("./jobs");
const { python } = require("./python");
const stageLib = require("./stage");
const { persist } = require("./datasync");
const { sticky } = require("./comment");

const root = path.resolve(__dirname, "..", "..");

// The data branch can live in another repository, pushed with its own token, to share one leaderboard.
function remote() {
  const repo = input("data-repo") || env.GITHUB_REPOSITORY;
  const token = input("data-token") || input("token");
  return { repo, url: `${env.GITHUB_SERVER_URL}/${repo}.git`.replace("https://", `https://x-access-token:${token}@`) };
}

// `*` matches anything and everything else is literal, so `*[bot]` skips every bot.
function ignored(name, patterns) {
  const n = String(name || "").trim().toLowerCase();
  return patterns
    .toLowerCase()
    .split(/[\s,]+/)
    .some((p) => p && new RegExp(`^${p.split("*").map((s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join(".*")}$`).test(n));
}

async function post() {
  const player = input("player") || env.GITHUB_ACTOR;
  if (ignored(player, input("ignore"))) {
    return log(`QuestOps: ${player} is on the ignore list. The dungeon pretends not to notice.`);
  }
  let outcome = input("outcome");
  if (!outcome || outcome === "auto") {
    try {
      outcome = await jobOutcome();
    } catch (e) {
      return warn(`${e.message}; skipping the encounter.`);
    }
  }
  const doPersist = input("persist") !== "false";
  const branch = input("data-branch") || "questops-data";
  const dir = path.join(env.RUNNER_TEMP, "questops-data");
  const script = path.join(root, "scripts", "data-branch.sh");
  const { repo: dataRepo, url } = remote();

  const args = ["-m", "questops", "quest", "--outcome", outcome, "--player", player, "--kind", input("kind") || "random"];
  if (input("seed")) args.push("--seed", input("seed"));
  if (!doPersist) args.push("--dry-run");
  const stage = path.join(env.RUNNER_TEMP, "questops-stage");
  const play = () => {
    const staged = stageLib.reset(stage);
    const vars = { ...env, ...staged, PYTHONPATH: path.join(root, "src"), QUESTOPS_DATA_DIR: dir, QUESTOPS_DATA_BRANCH: branch, QUESTOPS_DATA_REPO: dataRepo };
    return run(python(), args, { stdio: ["inherit", "pipe", "inherit"], encoding: "utf8", env: vars });
  };
  let commentMd = "";
  const publish = (r) => {
    stageLib.publish(stage, r, input("summary") !== "false");
    commentMd = stageLib.comment(stage);
  };
  const comment = () => (input("comment") === "true" && commentMd ? sticky(commentMd) : undefined);

  if (!doPersist) {
    const r = play();
    publish(r);
    if (r.status !== 0) warn(`encounter exited with ${r.status}`);
    return comment();
  }
  await persist({ script, dir, branch, url, player, outcome, play, publish });
  await comment();
}

module.exports = { post, remote };
