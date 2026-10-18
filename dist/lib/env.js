"use strict";
const { spawnSync } = require("child_process");

const env = process.env;
const input = (n) => (env[`INPUT_${n.toUpperCase()}`] || "").trim();
const log = (m) => console.log(m);
const warn = (m) => console.log(`::warning::QuestOps: ${m}`);

function run(cmd, args, opts = {}) {
  return spawnSync(cmd, args, { stdio: "inherit", env, ...opts });
}

module.exports = { env, input, log, warn, run };
