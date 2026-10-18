"use strict";
const fs = require("fs");
const path = require("path");
const { env, log } = require("./env");

// A retried quest is replayed from scratch, so each attempt writes to a fresh staging directory and
// only the attempt that sticks is published to the log, the job summary and the step outputs.
// The pull request comment is staged the same way, but is only read by the comment step.
function reset(stage) {
  fs.rmSync(stage, { recursive: true, force: true });
  fs.mkdirSync(stage, { recursive: true });
  return { GITHUB_OUTPUT: path.join(stage, "output"), GITHUB_STEP_SUMMARY: path.join(stage, "summary"), QUESTOPS_COMMENT_FILE: path.join(stage, "comment") };
}

function publish(stage, r, withSummary = true) {
  log(r.stdout.trimEnd());
  for (const [name, target] of [["output", env.GITHUB_OUTPUT], ["summary", withSummary && env.GITHUB_STEP_SUMMARY]]) {
    const file = path.join(stage, name);
    if (target && fs.existsSync(file)) fs.appendFileSync(target, fs.readFileSync(file));
  }
}

function comment(stage) {
  const file = path.join(stage, "comment");
  return fs.existsSync(file) ? fs.readFileSync(file, "utf8") : "";
}

module.exports = { reset, publish, comment };
