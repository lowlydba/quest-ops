"use strict";
const { env, log, warn, run } = require("./env");

const attempts = 10;

const pull = (script, dir, branch, url) => run("bash", [script, "pull", dir, branch, url]).status;
const push = (script, dir, branch, message) => run("bash", [script, "push", dir, branch, message]).status;

// Concurrent runs race for the data branch. Never merge: pull the latest, play, push, and if
// someone else pushed first (exit 75), throw our attempt away and redo it on top of their result.
async function persist({ script, dir, branch, url, player, outcome, play, publish }) {
  for (let n = 1; n <= attempts; n++) {
    if (pull(script, dir, branch, url) !== 0) return warn("could not fetch the data branch");
    const r = play();
    if (r.status !== 0) {
      publish(r);
      return warn(`encounter exited with ${r.status}`);
    }
    if (outcome === "cancelled" || outcome === "skipped") return publish(r);
    const status = push(script, dir, branch, `questops: ${player} - ${outcome}`);
    if (status === 0) return publish(r);
    if (status !== 75) {
      publish(r);
      return warn("could not push the data branch");
    }
    if (n < attempts) {
      const wait = env.QUESTOPS_RETRY_DELAY_MS ? Number(env.QUESTOPS_RETRY_DELAY_MS) : 500 + Math.floor(Math.random() * 1500) * n;
      log(`QuestOps: another run pushed first; trying again in ${wait} ms (${n}/${attempts - 1})`);
      await new Promise((resolve) => setTimeout(resolve, wait));
    }
  }
  warn("gave up after repeated races for the data branch");
}

module.exports = { persist, pull, push, attempts };
