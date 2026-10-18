// QuestOps GitHub Action shim (Node builtins only, no dependencies).
// main: does nothing but arm the hook. post: runs at the very end of the job
// (post-if: always()), works out how the job actually went, then runs QuestOps.
"use strict";
const fs = require("fs");
const { env, log, warn } = require("./lib/env");
const { jobOutcome } = require("./lib/jobs");
const { python } = require("./lib/python");
const { post } = require("./lib/post");

// What the dungeon says while it waits for the job to finish. One is picked per run.
const OMENS = [
  "A door grinds open somewhere below. Whatever is behind it will be waiting when this job finishes.",
  "Torches flicker to life down the corridor. Your encounter begins the moment this job ends.",
  "Something in the dark has started reading your test output. It makes its move when the job is done.",
  "The dice are cast, but they haven't landed. This job decides how they fall.",
  "A bard tunes up in the tavern, ready to sing of this run. The ending depends on the job.",
  "Far below, a monster stretches. It has until the end of this job to warm up.",
];

function omen(seed = env.GITHUB_RUN_ID || "") {
  let h = 0;
  for (const c of String(seed)) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return `QuestOps: ${OMENS[h % OMENS.length]}`;
}

async function main() {
  if (env.STATE_questopsPost !== "true") {
    fs.appendFileSync(env.GITHUB_STATE, "questopsPost=true\n");
    return log(omen());
  }
  await post();
}

module.exports = { jobOutcome, post, main, python, omen, OMENS };

if (require.main === module) main().catch((e) => warn(e.message));
